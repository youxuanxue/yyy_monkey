from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
import sqlite3

from .db import get_conn
from .rate_limit import check_and_increment_per_minute


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def audit(
    event_type: str,
    entity_type: str,
    entity_id: str,
    data: dict,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    """
    审计写入必须尽量复用当前事务连接，避免 SQLite 两连接抢写锁导致 "database is locked"。
    - 若传入 conn：使用同一连接写入（不在此函数内 commit）
    - 若不传：自行开连接并 commit（用于独立事件）
    """
    if conn is not None:
        conn.execute(
            "INSERT INTO audit_logs(id, event_type, entity_type, entity_id, data_json, created_at) VALUES(?,?,?,?,?,?)",
            (new_id("audit"), event_type, entity_type, entity_id, json.dumps(data, ensure_ascii=False), now_iso()),
        )
        return

    c = get_conn()
    try:
        c.execute(
            "INSERT INTO audit_logs(id, event_type, entity_type, entity_id, data_json, created_at) VALUES(?,?,?,?,?,?)",
            (new_id("audit"), event_type, entity_type, entity_id, json.dumps(data, ensure_ascii=False), now_iso()),
        )
        c.commit()
    finally:
        c.close()


COMMENT_RATE_LIMIT_PER_MINUTE = 2


def create_like_tasks_for_run(run_id: str) -> int:
    """
    MVP 简化：对 run 下所有 candidates 生成 like 任务（若不存在）。
    """
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id FROM candidates WHERE run_id=?", (run_id,)).fetchall()
        created = 0
        for r in rows:
            candidate_id = r["id"]
            exists = conn.execute(
                "SELECT 1 FROM action_tasks WHERE candidate_id=? AND action_type='like' LIMIT 1",
                (candidate_id,),
            ).fetchone()
            if exists:
                continue
            task_id = new_id("task")
            now = now_iso()
            conn.execute(
                "INSERT INTO action_tasks(id, candidate_id, action_type, status, payload_json, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (task_id, candidate_id, "like", "queued", "{}", now, now),
            )
            created += 1
            audit(
                "action_task_created",
                "action_task",
                task_id,
                {"action_type": "like", "candidate_id": candidate_id},
                conn=conn,
            )
        conn.commit()
        return created
    finally:
        conn.close()


def _text_contains_any(text: str, needles: list[str]) -> bool:
    t = (text or "").lower()
    for n in needles:
        n = (n or "").strip().lower()
        if not n:
            continue
        if n in t:
            return True
    return False


def create_comment_tasks_for_run(run_id: str) -> int:
    """
    MVP 策略引擎（极简）：
    - 仅当 job.comment_enabled=1 时生成 comment_submit 任务
    - 候选需命中 topic.keywords（若 keywords 为空则视为不生成）
    - 命中 exclude_keywords 则拒绝
    - 评论文本来自“最近创建的 enabled 模板”（模板白名单的一种实现）
    """
    conn = get_conn()
    try:
        meta = conn.execute(
            "SELECT jobs.comment_enabled as comment_enabled, jobs.topic_id as topic_id, "
            "topics.keywords as keywords, topics.exclude_keywords as exclude_keywords "
            "FROM runs JOIN jobs ON runs.job_id=jobs.id "
            "JOIN topics ON jobs.topic_id=topics.id "
            "WHERE runs.id=?",
            (run_id,),
        ).fetchone()
        if meta is None:
            return 0
        if int(meta["comment_enabled"]) != 1:
            return 0

        keywords = json.loads(meta["keywords"])
        exclude_keywords = json.loads(meta["exclude_keywords"])
        if not keywords:
            return 0

        tpl = conn.execute(
            "SELECT id, body FROM comment_templates WHERE enabled=1 ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if tpl is None:
            return 0
        template_id = tpl["id"]
        comment_text = tpl["body"]

        rows = conn.execute(
            "SELECT id, title, raw_text FROM candidates WHERE run_id=? ORDER BY created_at ASC",
            (run_id,),
        ).fetchall()

        created = 0
        for r in rows:
            candidate_id = r["id"]
            exists = conn.execute(
                "SELECT 1 FROM action_tasks WHERE candidate_id=? AND action_type='comment_submit' LIMIT 1",
                (candidate_id,),
            ).fetchone()
            if exists:
                continue

            hay = f"{r['title'] or ''}\n{r['raw_text'] or ''}"
            if _text_contains_any(hay, exclude_keywords):
                continue
            if not _text_contains_any(hay, keywords):
                continue

            # 生成任务本身用 create_comment_task（含长度/关键词过滤/模板校验）
            task_id = create_comment_task(candidate_id, template_id, comment_text)
            if task_id:
                created += 1

        return created
    finally:
        conn.close()


def create_comment_task(candidate_id: str, template_id: str, comment_text: str) -> str | None:
    """
    生成 comment_submit 任务前做门禁：
    - 模板必须 enabled
    - 文本过滤（MVP：极简）
    """
    comment_text = (comment_text or "").strip()
    if not comment_text:
        return None
    if len(comment_text) > 50:
        return None

    blocked_keywords = ["vx", "微信", "加群", "私信", "联系方式", "二维码", "链接", "淘宝", "拼多多"]
    lowered = comment_text.lower()
    if any(k in lowered for k in blocked_keywords):
        return None

    conn = get_conn()
    try:
        tpl = conn.execute(
            "SELECT id FROM comment_templates WHERE id=? AND enabled=1",
            (template_id,),
        ).fetchone()
        if tpl is None:
            return None

        task_id = new_id("task")
        now = now_iso()
        payload = {"template_id": template_id, "comment_text": comment_text}
        conn.execute(
            "INSERT INTO action_tasks(id, candidate_id, action_type, status, payload_json, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (task_id, candidate_id, "comment_submit", "queued", json.dumps(payload, ensure_ascii=False), now, now),
        )
        audit(
            "action_task_created",
            "action_task",
            task_id,
            {"action_type": "comment_submit", "candidate_id": candidate_id},
            conn=conn,
        )
        conn.commit()
        return task_id
    finally:
        conn.close()


def pop_next_task(account_id: str) -> dict | None:
    """
    MVP：按 queued FIFO 弹出一条任务并置为 running。
    对 comment_submit 做速率门禁：每账号每分钟<=2。
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT action_tasks.id as id, action_tasks.candidate_id as candidate_id, action_tasks.action_type as action_type, "
            "action_tasks.payload_json as payload_json, candidates.url as candidate_url, candidates.title as candidate_title "
            "FROM action_tasks "
            "JOIN candidates ON candidates.id = action_tasks.candidate_id "
            "WHERE action_tasks.status='queued' "
            "ORDER BY action_tasks.created_at ASC LIMIT 1"
        ).fetchone()
        if row is None:
            return None

        task_id = row["id"]
        action_type = row["action_type"]

        if action_type == "comment_submit":
            rl = check_and_increment_per_minute(f"comment:{account_id}", COMMENT_RATE_LIMIT_PER_MINUTE)
            if not rl.allowed:
                # 不弹出，保持 queued（下一分钟再试）
                return None

        now = now_iso()
        conn.execute("UPDATE action_tasks SET status='running', updated_at=? WHERE id=?", (now, task_id))
        audit("action_task_dispatched", "action_task", task_id, {"account_id": account_id, "action_type": action_type}, conn=conn)
        conn.commit()

        return {
            "id": task_id,
            "candidate_id": row["candidate_id"],
            "candidate_url": row["candidate_url"],
            "candidate_title": row["candidate_title"],
            "action_type": action_type,
            "payload": json.loads(row["payload_json"]),
        }
    finally:
        conn.close()


def report_task(task_id: str, status: str, error_message: str | None, evidence: dict | None) -> None:
    conn = get_conn()
    try:
        now = now_iso()
        conn.execute(
            "UPDATE action_tasks SET status=?, error_message=?, updated_at=? WHERE id=?",
            (status, error_message, now, task_id),
        )
        audit(
            "action_task_reported",
            "action_task",
            task_id,
            {"status": status, "error_message": error_message, "evidence": evidence or {}},
            conn=conn,
        )
        conn.commit()
    finally:
        conn.close()


