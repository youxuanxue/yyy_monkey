"""
日更内容规划生成器

基于分析报告 + 目标定位 + 风格约束 + 栏目体系，
生成 1 个月日更规划 Markdown（30 篇选题 + 5 篇备用）。

使用 LLM（OpenAI 兼容 API）辅助生成差异化选题和提纲，
由规则层把关栏目分配、去重和风格校验。
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _get_llm_client() -> OpenAI:
    """获取 OpenAI 兼容的 LLM 客户端"""
    base_url = os.environ.get("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", ""))
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "未配置 LLM API key。请设置环境变量 OPENAI_API_KEY，"
            "如使用 DeepSeek/Qwen，同时设置 OPENAI_BASE_URL。"
        )
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _build_system_prompt(config: dict, analysis: dict) -> str:
    """构建 LLM 的系统提示词"""
    target = config.get("target", {})
    family = target.get("family", {})
    style_profile = analysis.get("style_profile", {})
    covered = analysis.get("covered_topics", [])
    insights = analysis.get("reference_insights", [])
    recommendations = analysis.get("recommended_directions", [])

    ref_top_articles = []
    for ins in insights:
        for art in ins.get("top_articles", [])[:3]:
            ref_top_articles.append(f"  - [{ins['name']}] {art['title']}")

    return f"""你是一个微信公众号内容策划专家。你需要为公众号「{target.get('name', '懿起成长')}」生成日更选题规划。

## 账号定位
{target.get('positioning', '')}

## 家庭成员
- {family.get('dad', '懿爸')}
- {family.get('son', '大懿')}
- {family.get('daughter', '小懿')}

## 写作风格要求
- {target.get('style_notes', '')}
- 叙事人称: {style_profile.get('narrative_voice', '第一人称')}
- 平均文章长度: {style_profile.get('avg_article_length', 1500)} 字左右
- 标题风格: 朴实、具体、不营销化，平均 {style_profile.get('title_avg_length', 15)} 字
- 高频表达: {', '.join(e[0] for e in style_profile.get('top_expressions', [])[:5])}

## 已发过的主题（避免重复）
{', '.join(covered)}

## 参考公众号高互动文章样本
{chr(10).join(ref_top_articles) if ref_top_articles else '暂无数据'}

## 建议的内容方向
{chr(10).join(f'- {r}' for r in recommendations)}

## 核心禁忌
1. 禁止 AI 写作特征：不要用"让我们"、"值得一提的是"、"总的来说"、"不得不说"等套话
2. 禁止鸡汤升华：不要在结尾强行总结人生道理
3. 禁止完美叙事：每个故事要有真实的粗糙感——犹豫、错误、尴尬
4. 标题禁止营销词："必看"、"震惊"、"干货"、"逆袭"等一律不用
5. 所有故事场景必须具体到时间、地点、对话，不要泛泛而谈
6. 不要生搬硬套参考公众号的内容，要结合大懿和小懿的实际情况来写"""


def _build_column_prompt(columns: list[dict]) -> str:
    """构建栏目说明"""
    lines = ["## 栏目体系（每周固定轮转）"]
    for col in columns:
        wd = col.get("weekday", 0)
        wd_name = WEEKDAY_NAMES[wd - 1] if 1 <= wd <= 7 else f"第{wd}天"
        lines.append(f"- {wd_name}·{col['name']}: {col['focus']}")
    return "\n".join(lines)


def _build_generation_prompt(
    start_date: datetime,
    days: int,
    columns: list[dict],
    existing_titles: list[str],
    spare_count: int = 5,
) -> str:
    """构建选题生成的用户提示词"""
    dates_info = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        wd = d.isoweekday()  # 1=Monday
        col = next((c for c in columns if c["weekday"] == wd), None)
        col_name = col["name"] if col else "自由选题"
        dates_info.append(
            f"Day {i+1} ({d.strftime('%m月%d日')} {WEEKDAY_NAMES[wd-1]}) — {col_name}"
        )

    existing_str = ""
    if existing_titles:
        existing_str = "\n\n## 已发文章标题（必须避免重复或高度相似）\n"
        for t in existing_titles:
            existing_str += f"- {t}\n"

    return f"""请为以下 {days} 天各生成 1 个选题，另外再生成 {spare_count} 个备用选题。

## 日期与栏目安排

{chr(10).join(dates_info)}
{existing_str}

## 输出要求

对每个选题，请严格按以下 JSON 格式输出，整体输出一个 JSON 数组：

```json
[
  {{
    "day": 1,
    "date": "03月03日",
    "weekday": "周一",
    "column": "大懿成长记",
    "title": "大懿说他不想当班长了",
    "outline": [
      "大懿回家说了什么（原话还原）",
      "我的第一反应和内心活动",
      "晚饭时跟他聊了聊，他的真实想法",
      "想起自己小时候类似的经历"
    ],
    "scene": "周五放学接大懿，车上他突然说不想当班长。追问才知道是因为要管纪律被同学说'多管闲事'。",
    "writing_tips": [
      "不要给结论，记录过程就好",
      "可以写自己的犹豫（要不要去找老师）",
      "结尾留开放式，不升华"
    ],
    "is_spare": false
  }}
]
```

备用选题的 `day` 设为 0，`is_spare` 设为 true，`date` 和 `weekday` 留空。

关键要求：
1. 每个故事场景必须具体、生动，包含对话和细节
2. 标题要朴实自然，像在跟朋友说话
3. 提纲 3-5 点，点与点之间有叙事推进
4. 写作要点要具体，不要泛泛的"注意真实感"
5. 30 个日常选题 + {spare_count} 个备用选题，共 {days + spare_count} 个
6. 不同栏目的选题要贴合栏目定位"""


def generate_plan(
    config: dict,
    analysis_path: Path,
    output_dir: Path,
    log_fn=None,
):
    """
    生成日更内容规划

    Args:
        config: target.json 配置
        analysis_path: analysis_report.json 路径
        output_dir: 输出目录
        log_fn: 日志函数
    """
    _log = log_fn or (lambda msg: logger.info(msg))

    # 读取分析报告
    if not analysis_path.exists():
        _log(f"未找到分析报告: {analysis_path}，请先运行 analyze 命令")
        return
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    # 配置参数
    plan_config = config.get("plan_config", {})
    days = plan_config.get("duration_days", 30)
    spare = plan_config.get("spare_topics", 5)
    columns = analysis.get("suggested_columns") or config.get("columns", [])

    start_date_str = plan_config.get("start_date", "auto")
    if start_date_str == "auto":
        start_date = datetime.now() + timedelta(days=1)
    else:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

    # 已发文章标题（用于去重）
    existing_titles = [
        a.get("title", "")
        for a in analysis.get("target", {}).get("article_list", [])
        if a.get("title")
    ]

    _log("正在调用 LLM 生成选题...")
    _log(f"  起始日期: {start_date.strftime('%Y-%m-%d')}")
    _log(f"  天数: {days} 天 + {spare} 备用")
    _log(f"  栏目: {len(columns)} 个")

    # 构建提示词
    system = _build_system_prompt(config, analysis)
    system += "\n\n" + _build_column_prompt(columns)
    user = _build_generation_prompt(start_date, days, columns, existing_titles, spare)

    # 调用 LLM
    client = _get_llm_client()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.8,
        max_tokens=8000,
    )

    raw_text = response.choices[0].message.content
    _log("LLM 响应已收到，正在解析...")

    # 解析 JSON
    topics = _parse_topics_from_response(raw_text, _log)
    if not topics:
        _log("解析选题失败，将原始响应保存为文本")
        fallback_path = output_dir / "plans" / "raw_response.txt"
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        fallback_path.write_text(raw_text, encoding="utf-8")
        _log(f"原始响应已保存: {fallback_path}")
        return

    # 生成 Markdown 规划文档
    md = _build_plan_markdown(topics, start_date, config)
    plans_dir = output_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    filename = f"plan_{start_date.strftime('%Y%m%d')}_{days}d.md"
    md_path = plans_dir / filename
    md_path.write_text(md, encoding="utf-8")

    # 同时保存 JSON
    json_path = plans_dir / filename.replace(".md", ".json")
    json_path.write_text(
        json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _log(f"\n日更规划已生成！")
    _log(f"  Markdown: {md_path}")
    _log(f"  JSON: {json_path}")
    _log(f"  共 {sum(1 for t in topics if not t.get('is_spare'))} 篇日常选题")
    _log(f"  共 {sum(1 for t in topics if t.get('is_spare'))} 篇备用选题")


def _parse_topics_from_response(text: str, log_fn) -> list[dict]:
    """从 LLM 响应中解析选题 JSON"""
    import re

    # 尝试提取 JSON 数组
    # 先尝试 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*\n(\[[\s\S]*?\])\s*\n```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            log_fn(f"JSON 解析失败（代码块）: {e}")

    # 尝试直接找最外层 [ ... ]
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            log_fn(f"JSON 解析失败（裸数组）: {e}")

    return []


def _build_plan_markdown(
    topics: list[dict],
    start_date: datetime,
    config: dict,
) -> str:
    """构建规划 Markdown 文档"""
    target_name = config.get("target", {}).get("name", "懿起成长")
    plan_config = config.get("plan_config", {})
    days = plan_config.get("duration_days", 30)
    end_date = start_date + timedelta(days=days - 1)

    lines = []
    lines.append(f"# 「{target_name}」日更内容规划\n")
    lines.append(
        f"> 规划周期: {start_date.strftime('%Y年%m月%d日')} - "
        f"{end_date.strftime('%Y年%m月%d日')}\n"
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    )

    # 日常选题
    daily = [t for t in topics if not t.get("is_spare")]
    spare = [t for t in topics if t.get("is_spare")]

    lines.append(f"## 日常选题（{len(daily)} 篇）\n")

    current_week = None
    for t in sorted(daily, key=lambda x: x.get("day", 0)):
        day = t.get("day", 0)
        week_num = (day - 1) // 7 + 1
        if week_num != current_week:
            current_week = week_num
            lines.append(f"\n---\n\n### 第 {week_num} 周\n")

        lines.append(
            f"#### Day {day} ({t.get('date', '')}"
            f" {t.get('weekday', '')}) — {t.get('column', '')}\n"
        )
        lines.append(f"**标题**: {t.get('title', '')}\n")

        outline = t.get("outline", [])
        if outline:
            lines.append("**提纲**:\n")
            for i, o in enumerate(outline, 1):
                lines.append(f"{i}. {o}")
            lines.append("")

        scene = t.get("scene", "")
        if scene:
            lines.append(f"**故事场景**: {scene}\n")

        tips = t.get("writing_tips", [])
        if tips:
            lines.append("**写作要点**:\n")
            for tip in tips:
                lines.append(f"- {tip}")
            lines.append("")

    # 备用选题
    if spare:
        lines.append(f"\n---\n\n## 备用选题（{len(spare)} 篇）\n")
        for i, t in enumerate(spare, 1):
            lines.append(f"#### 备用 {i} — {t.get('column', '自由选题')}\n")
            lines.append(f"**标题**: {t.get('title', '')}\n")
            outline = t.get("outline", [])
            if outline:
                lines.append("**提纲**:\n")
                for j, o in enumerate(outline, 1):
                    lines.append(f"{j}. {o}")
                lines.append("")
            scene = t.get("scene", "")
            if scene:
                lines.append(f"**故事场景**: {scene}\n")

    lines.append("\n---\n")
    lines.append("*本规划由 creator 工具生成，选题和提纲仅供参考，写作时请结合真实生活素材。*\n")

    return "\n".join(lines)
