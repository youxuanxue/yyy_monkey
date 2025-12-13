from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from .db import init_db, get_conn
from .models import (
    ActionTaskNextReq,
    ActionTaskNextResp,
    ActionTaskReportReq,
    CandidateBatchUpsert,
    CandidateBatchUpsertResp,
    CommentTemplateCreate,
    CommentTemplateOut,
    HealthResponse,
    JobCreate,
    JobOut,
    RunCreate,
    RunOut,
    TopicCreate,
    TopicOut,
)
from .service import (
    audit,
    create_comment_task,
    create_comment_tasks_for_run,
    create_like_tasks_for_run,
    new_id,
    now_iso,
    pop_next_task,
    report_task,
)


VERSION = "0.1.0"

app = FastAPI(title="yyy_monkey local_service", version=VERSION)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION)


@app.post("/v1/topics", response_model=TopicOut)
def create_topic(req: TopicCreate) -> TopicOut:
    topic_id = new_id("topic")
    now = now_iso()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO topics(id, name, keywords, exclude_keywords, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (topic_id, req.name, json.dumps(req.keywords, ensure_ascii=False), json.dumps(req.exclude_keywords, ensure_ascii=False), now, now),
        )
        conn.commit()
    finally:
        conn.close()
    audit("topic_created", "topic", topic_id, req.model_dump())
    return TopicOut(
        id=topic_id,
        name=req.name,
        keywords=req.keywords,
        exclude_keywords=req.exclude_keywords,
        created_at=now,
        updated_at=now,
    )


@app.get("/v1/topics", response_model=list[TopicOut])
def list_topics() -> list[TopicOut]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM topics ORDER BY created_at DESC").fetchall()
        out: list[TopicOut] = []
        for r in rows:
            out.append(
                TopicOut(
                    id=r["id"],
                    name=r["name"],
                    keywords=json.loads(r["keywords"]),
                    exclude_keywords=json.loads(r["exclude_keywords"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
            )
        return out
    finally:
        conn.close()


@app.post("/v1/jobs", response_model=JobOut)
def create_job(req: JobCreate) -> JobOut:
    job_id = new_id("job")
    now = now_iso()
    like_enabled = bool(req.actions.get("like_enabled", True))
    comment_enabled = bool(req.actions.get("comment_enabled", False))
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO jobs(id, topic_id, schedule, enabled, like_enabled, comment_enabled, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (job_id, req.topic_id, req.schedule, 1 if req.enabled else 0, 1 if like_enabled else 0, 1 if comment_enabled else 0, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    audit("job_created", "job", job_id, req.model_dump())
    return JobOut(
        id=job_id,
        topic_id=req.topic_id,
        schedule=req.schedule,
        enabled=req.enabled,
        like_enabled=like_enabled,
        comment_enabled=comment_enabled,
        created_at=now,
        updated_at=now,
    )


@app.post("/v1/runs", response_model=RunOut)
def create_run(req: RunCreate) -> RunOut:
    run_id = new_id("run")
    now = now_iso()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO runs(id, job_id, status, started_at, ended_at) VALUES(?,?,?,?,?)",
            (run_id, req.job_id, "running", now, None),
        )
        conn.commit()
    finally:
        conn.close()
    audit("run_created", "run", run_id, req.model_dump())
    return RunOut(id=run_id, job_id=req.job_id, status="running", started_at=now, ended_at=None)


@app.post("/v1/candidates:batchUpsert", response_model=CandidateBatchUpsertResp)
def batch_upsert_candidates(req: CandidateBatchUpsert) -> CandidateBatchUpsertResp:
    conn = get_conn()
    now = now_iso()
    try:
        job = conn.execute(
            "SELECT jobs.id as job_id, jobs.topic_id as topic_id FROM runs JOIN jobs ON runs.job_id=jobs.id WHERE runs.id=?",
            (req.run_id,),
        ).fetchone()
        if job is None:
            raise HTTPException(status_code=404, detail="run not found")
        topic_id = job["topic_id"]

        candidate_ids: list[str] = []
        for item in req.items:
            cid = new_id("cand")
            try:
                conn.execute(
                    "INSERT INTO candidates(id, run_id, topic_id, source, url, video_id, author_name, title, raw_text, created_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (cid, req.run_id, topic_id, item.source, item.url, item.video_id, item.author_name, item.title, item.raw_text, now),
                )
                candidate_ids.append(cid)
                audit(
                    "candidate_created",
                    "candidate",
                    cid,
                    {"run_id": req.run_id, "url": item.url, "source": item.source},
                    conn=conn,
                )
            except Exception:
                # UNIQUE(run_id, url) 冲突则忽略，MVP 简化
                pass

        conn.commit()
    finally:
        conn.close()

    # MVP 简化：上报后自动生成 like 任务（如果你不想这样，可以改成由 Scheduler/Run end 时生成）
    create_like_tasks_for_run(req.run_id)
    # MVP 简化：策略引擎自动生成 comment_submit 任务（仅当 job.comment_enabled=1 且命中关键词/排除词规则）
    create_comment_tasks_for_run(req.run_id)
    return CandidateBatchUpsertResp(candidate_ids=candidate_ids)


@app.post("/v1/actionTasks:next", response_model=ActionTaskNextResp)
def next_action_task(req: ActionTaskNextReq) -> ActionTaskNextResp:
    task = pop_next_task(req.account_id)
    return ActionTaskNextResp(task=task)


@app.post("/v1/actionTasks/{task_id}:report")
def report_action_task(task_id: str, req: ActionTaskReportReq) -> dict:
    report_task(task_id, req.status, req.error_message, req.evidence)
    return {"ok": True}


@app.get("/v1/commentTemplates", response_model=list[CommentTemplateOut])
def list_comment_templates() -> list[CommentTemplateOut]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM comment_templates ORDER BY created_at DESC").fetchall()
        out: list[CommentTemplateOut] = []
        for r in rows:
            out.append(
                CommentTemplateOut(
                    id=r["id"],
                    name=r["name"],
                    body=r["body"],
                    enabled=bool(r["enabled"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                )
            )
        return out
    finally:
        conn.close()


@app.post("/v1/commentTemplates", response_model=CommentTemplateOut)
def create_comment_template(req: CommentTemplateCreate) -> CommentTemplateOut:
    tpl_id = new_id("tpl")
    now = now_iso()
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO comment_templates(id, name, body, enabled, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (tpl_id, req.name, req.body, 1 if req.enabled else 0, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    audit("comment_template_created", "comment_template", tpl_id, req.model_dump())
    return CommentTemplateOut(id=tpl_id, name=req.name, body=req.body, enabled=req.enabled, created_at=now, updated_at=now)


@app.post("/v1/candidates/{candidate_id}:enqueueAutoComment")
def enqueue_auto_comment(candidate_id: str) -> dict:
    """
    MVP 便捷接口：基于第一条启用模板为候选创建自动评论任务。
    真正产品里应该由 Policy Engine 决策是否生成。
    """
    conn = get_conn()
    try:
        tpl = conn.execute("SELECT id, body FROM comment_templates WHERE enabled=1 ORDER BY created_at DESC LIMIT 1").fetchone()
        if tpl is None:
            raise HTTPException(status_code=400, detail="no enabled comment template")
        template_id = tpl["id"]
        comment_text = tpl["body"]
    finally:
        conn.close()

    task_id = create_comment_task(candidate_id, template_id, comment_text)
    if task_id is None:
        raise HTTPException(status_code=400, detail="comment gate rejected (empty/filtered/too long/template disabled)")
    return {"task_id": task_id}


