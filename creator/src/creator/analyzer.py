"""
内容分析器

分两层分析抓取到的公众号文章数据：
1. 目标账号深度分析：风格画像、主题分布、已用素材
2. 参考账号对标分析：主题聚类、互动率排名、高互动特征

输出：Markdown 可读报告 + JSON 结构化数据
"""

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 育儿/家庭类文章的主题关键词映射
TOPIC_KEYWORDS = {
    "学习/教育": [
        "作业", "考试", "成绩", "分数", "学习", "辅导", "老师", "学校",
        "课堂", "教育", "补习", "培训", "阅读", "写字", "数学", "语文",
        "英语", "课外", "奥数", "拼音", "识字", "背诵", "默写", "练习",
    ],
    "成长/心理": [
        "成长", "心理", "情绪", "焦虑", "自信", "独立", "叛逆", "青春期",
        "性格", "脾气", "哭", "闹", "害怕", "勇敢", "坚持", "放弃",
        "挫折", "鼓励", "表扬", "批评", "沟通",
    ],
    "亲子/陪伴": [
        "陪伴", "亲子", "爸爸", "妈妈", "父母", "家长", "带娃", "遛娃",
        "周末", "假期", "旅行", "出游", "公园", "游乐", "博物馆",
        "手工", "游戏", "玩",
    ],
    "兄弟姐妹/二胎": [
        "兄妹", "兄弟", "姐妹", "二胎", "老大", "老二", "争", "吵",
        "分享", "抢", "偏心", "公平", "哥哥", "姐姐", "弟弟", "妹妹",
    ],
    "生活/日常": [
        "日常", "生活", "吃饭", "睡觉", "起床", "早餐", "晚饭",
        "家务", "做饭", "打扫", "洗澡", "穿衣", "买菜",
    ],
    "育儿观/反思": [
        "反思", "感悟", "育儿", "教养", "理念", "方法", "经验",
        "后悔", "错误", "道歉", "改变", "内卷", "鸡娃", "佛系",
        "躺平", "焦虑",
    ],
    "兴趣/特长": [
        "兴趣", "特长", "钢琴", "画画", "舞蹈", "运动", "足球",
        "篮球", "游泳", "跑步", "围棋", "编程", "乐高", "科学",
    ],
    "技术/工具": [
        "代码", "程序", "工具", "脚本", "AI", "自动化", "Python",
        "开发", "软件", "API", "浏览器", "自动", "GitHub",
    ],
}


def classify_topic(title: str, content: str = "") -> list[str]:
    """根据标题和内容关键词判断文章主题（可多标签）"""
    text = f"{title} {content[:500]}"
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                topics.append(topic)
                break
    return topics if topics else ["其他"]


def analyze_title_style(titles: list[str]) -> dict:
    """分析标题风格特征"""
    lengths = [len(t) for t in titles]
    has_question = sum(1 for t in titles if "？" in t or "?" in t)
    has_number = sum(1 for t in titles if re.search(r"\d", t))
    has_colon = sum(1 for t in titles if "：" in t or ":" in t)
    has_ellipsis = sum(1 for t in titles if "…" in t or "..." in t)
    total = len(titles) or 1

    return {
        "avg_length": round(sum(lengths) / total, 1),
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
        "question_ratio": round(has_question / total, 2),
        "number_ratio": round(has_number / total, 2),
        "colon_ratio": round(has_colon / total, 2),
        "ellipsis_ratio": round(has_ellipsis / total, 2),
    }


def analyze_writing_style(articles: list[dict]) -> dict:
    """分析写作风格特征（基于正文内容）"""
    if not articles:
        return {}

    contents = [a.get("content", "") for a in articles if a.get("content")]
    if not contents:
        return {"note": "无正文内容，无法分析写作风格"}

    avg_length = sum(len(c) for c in contents) / len(contents)

    # 统计人称使用
    first_person = sum(
        len(re.findall(r"我[^们]|我的|我们", c)) for c in contents
    )
    # 常用表达
    expressions = Counter()
    common_phrases = [
        "说实话", "其实", "后来", "结果", "没想到", "当时", "那天",
        "想起", "感觉", "发现", "突然", "终于", "大概", "估计",
        "可能", "反正", "不过", "但是", "然后", "于是",
    ]
    for c in contents:
        for phrase in common_phrases:
            cnt = c.count(phrase)
            if cnt:
                expressions[phrase] += cnt

    # 段落结构
    para_counts = []
    for c in contents:
        paras = [p.strip() for p in c.split("\n") if p.strip()]
        para_counts.append(len(paras))

    # 结尾模式
    endings = []
    for c in contents:
        lines = [l.strip() for l in c.strip().split("\n") if l.strip()]
        if lines:
            endings.append(lines[-1][:50])

    return {
        "article_count": len(contents),
        "avg_content_length": round(avg_length),
        "first_person_freq": first_person,
        "top_expressions": expressions.most_common(10),
        "avg_paragraph_count": round(sum(para_counts) / len(para_counts), 1) if para_counts else 0,
        "sample_endings": endings[:5],
    }


def analyze_interaction(articles: list[dict]) -> dict:
    """分析互动数据"""
    with_data = [
        a for a in articles
        if a.get("read_count", 0) > 0 or a.get("like_count", 0) > 0
    ]
    if not with_data:
        return {"note": "无互动数据"}

    reads = [a["read_count"] for a in with_data]
    likes = [a["like_count"] for a in with_data]

    sorted_by_read = sorted(with_data, key=lambda x: x.get("read_count", 0), reverse=True)
    top_articles = [
        {
            "title": a["title"],
            "read_count": a.get("read_count", 0),
            "like_count": a.get("like_count", 0),
            "create_date": a.get("create_date", ""),
        }
        for a in sorted_by_read[:10]
    ]

    return {
        "articles_with_data": len(with_data),
        "avg_read": round(sum(reads) / len(reads)),
        "max_read": max(reads),
        "avg_like": round(sum(likes) / len(likes)),
        "max_like": max(likes),
        "top_articles": top_articles,
    }


def _extract_mentioned_entities(articles: list[dict]) -> dict:
    """提取已提到的人物、场景等素材"""
    people = Counter()
    scenes = Counter()

    people_patterns = [
        r"大懿", r"小懿", r"懿爸", r"懿妈", r"老师", r"同学",
        r"爷爷", r"奶奶", r"外公", r"外婆",
    ]
    scene_patterns = [
        r"学校", r"教室", r"操场", r"公园", r"家里", r"厨房",
        r"书房", r"卧室", r"车上", r"超市", r"医院", r"图书馆",
        r"博物馆", r"游乐场", r"餐厅",
    ]

    for a in articles:
        text = f"{a.get('title', '')} {a.get('content', '')}"
        for p in people_patterns:
            cnt = len(re.findall(p, text))
            if cnt:
                people[p] += cnt
        for s in scene_patterns:
            cnt = len(re.findall(s, text))
            if cnt:
                scenes[s] += cnt

    return {
        "people": dict(people.most_common()),
        "scenes": dict(scenes.most_common()),
    }


# ------------------------------------------------------------------
# 主分析函数
# ------------------------------------------------------------------

def analyze_target(articles: list[dict]) -> dict:
    """深度分析目标账号"""
    # 主题分布
    topic_counter = Counter()
    for a in articles:
        topics = classify_topic(a.get("title", ""), a.get("content", ""))
        for t in topics:
            topic_counter[t] += 1

    return {
        "total_articles": len(articles),
        "topic_distribution": dict(topic_counter.most_common()),
        "title_style": analyze_title_style([a["title"] for a in articles]),
        "writing_style": analyze_writing_style(articles),
        "interaction": analyze_interaction(articles),
        "mentioned_entities": _extract_mentioned_entities(articles),
        "article_list": [
            {
                "title": a.get("title", ""),
                "create_date": a.get("create_date", ""),
                "topics": classify_topic(a.get("title", ""), a.get("content", "")),
                "read_count": a.get("read_count", 0),
                "like_count": a.get("like_count", 0),
            }
            for a in articles
        ],
    }


def analyze_reference(articles: list[dict], name: str) -> dict:
    """分析参考账号"""
    topic_counter = Counter()
    topic_reads = defaultdict(list)

    for a in articles:
        topics = classify_topic(a.get("title", ""), a.get("content", ""))
        for t in topics:
            topic_counter[t] += 1
            if a.get("read_count", 0) > 0:
                topic_reads[t].append(a["read_count"])

    topic_avg_reads = {
        t: round(sum(reads) / len(reads))
        for t, reads in topic_reads.items()
        if reads
    }

    return {
        "name": name,
        "total_articles": len(articles),
        "topic_distribution": dict(topic_counter.most_common()),
        "topic_avg_reads": topic_avg_reads,
        "title_style": analyze_title_style([a["title"] for a in articles]),
        "interaction": analyze_interaction(articles),
    }


def generate_report(
    target_analysis: dict,
    reference_analyses: list[dict],
    config: dict,
    output_dir: Path,
):
    """生成综合分析报告（Markdown + JSON）"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- JSON 报告 ---
    json_report = {
        "generated_at": datetime.now().isoformat(),
        "target": target_analysis,
        "references": reference_analyses,
        "style_profile": _build_style_profile(target_analysis),
        "covered_topics": list(target_analysis.get("topic_distribution", {}).keys()),
        "reference_insights": _build_reference_insights(reference_analyses),
        "recommended_directions": _build_recommendations(
            target_analysis, reference_analyses, config
        ),
        "suggested_columns": config.get("columns", []),
    }

    json_path = output_dir / "analysis_report.json"
    json_path.write_text(
        json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- Markdown 报告 ---
    md = _build_markdown_report(target_analysis, reference_analyses, config)
    md_path = output_dir / "analysis_report.md"
    md_path.write_text(md, encoding="utf-8")

    return json_path, md_path


def _build_style_profile(target: dict) -> dict:
    """构建风格画像"""
    ws = target.get("writing_style", {})
    ts = target.get("title_style", {})
    return {
        "narrative_voice": "第一人称为主" if ws.get("first_person_freq", 0) > 5 else "混合人称",
        "avg_article_length": ws.get("avg_content_length", 0),
        "title_avg_length": ts.get("avg_length", 0),
        "title_features": {
            "prefers_questions": ts.get("question_ratio", 0) > 0.3,
            "uses_numbers": ts.get("number_ratio", 0) > 0.3,
            "uses_colons": ts.get("colon_ratio", 0) > 0.3,
        },
        "top_expressions": ws.get("top_expressions", []),
        "avg_paragraphs": ws.get("avg_paragraph_count", 0),
    }


def _build_reference_insights(refs: list[dict]) -> list[dict]:
    """提炼参考账号洞察"""
    insights = []
    for ref in refs:
        top_topics = sorted(
            ref.get("topic_avg_reads", {}).items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        top_articles = ref.get("interaction", {}).get("top_articles", [])[:5]

        insights.append({
            "name": ref["name"],
            "top_topics_by_read": [{"topic": t, "avg_read": r} for t, r in top_topics],
            "top_articles": top_articles,
            "total_articles": ref["total_articles"],
        })
    return insights


def _build_recommendations(target: dict, refs: list[dict], config: dict) -> list[str]:
    """生成选题方向建议"""
    covered = set(target.get("topic_distribution", {}).keys())
    ref_popular = Counter()
    for ref in refs:
        for topic, avg_read in ref.get("topic_avg_reads", {}).items():
            ref_popular[topic] += avg_read

    recommendations = []

    # 参考账号中高互动但目标账号未覆盖的主题
    for topic, score in ref_popular.most_common():
        if topic not in covered and topic != "其他" and topic != "技术/工具":
            recommendations.append(
                f"新方向「{topic}」：参考账号中该主题互动表现好，目标账号尚未覆盖"
            )

    # 目标账号已有强项
    target_interaction = target.get("interaction", {})
    top_arts = target_interaction.get("top_articles", [])
    if top_arts:
        top_topics = set()
        for a in top_arts[:3]:
            top_topics.update(
                classify_topic(a.get("title", ""))
            )
        for t in top_topics:
            if t != "其他":
                recommendations.append(f"延续强项「{t}」：目标账号该主题历史互动表现好")

    if not recommendations:
        recommendations.append("建议均衡覆盖育儿、学习、亲子、生活等主题")

    return recommendations


def _build_markdown_report(
    target: dict,
    refs: list[dict],
    config: dict,
) -> str:
    """构建 Markdown 可读报告"""
    lines = []
    target_name = config.get("target", {}).get("name", "目标账号")

    lines.append(f"# 内容分析报告\n")
    lines.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # === 第一部分：目标账号 ===
    lines.append(f"## 一、目标账号「{target_name}」深度分析\n")
    lines.append(f"### 1.1 基本概况\n")
    lines.append(f"- 历史文章总数: **{target.get('total_articles', 0)}** 篇\n")

    ws = target.get("writing_style", {})
    if ws.get("avg_content_length"):
        lines.append(f"- 平均文章长度: **{ws['avg_content_length']}** 字\n")

    # 主题分布
    lines.append(f"### 1.2 主题分布\n")
    td = target.get("topic_distribution", {})
    if td:
        for topic, count in sorted(td.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {topic}: {count} 篇")
        lines.append("")

    # 标题风格
    lines.append(f"### 1.3 标题风格\n")
    ts = target.get("title_style", {})
    if ts:
        lines.append(f"- 平均标题长度: {ts.get('avg_length', 0)} 字")
        lines.append(f"- 疑问句比例: {ts.get('question_ratio', 0):.0%}")
        lines.append(f"- 含数字比例: {ts.get('number_ratio', 0):.0%}")
        lines.append(f"- 冒号分隔比例: {ts.get('colon_ratio', 0):.0%}")
        lines.append("")

    # 写作风格
    lines.append(f"### 1.4 写作风格\n")
    if ws:
        lines.append(f"- 叙事人称: {'第一人称为主' if ws.get('first_person_freq', 0) > 5 else '混合人称'}")
        lines.append(f"- 平均段落数: {ws.get('avg_paragraph_count', 0)}")
        top_expr = ws.get("top_expressions", [])
        if top_expr:
            expr_str = "、".join(f"「{e[0]}」({e[1]}次)" for e in top_expr[:8])
            lines.append(f"- 高频表达: {expr_str}")
        endings = ws.get("sample_endings", [])
        if endings:
            lines.append(f"- 结尾样本:")
            for e in endings:
                lines.append(f"  - {e}")
        lines.append("")

    # 已使用素材
    lines.append(f"### 1.5 已使用素材\n")
    entities = target.get("mentioned_entities", {})
    people = entities.get("people", {})
    scenes = entities.get("scenes", {})
    if people:
        lines.append(f"- 提到的人物: {', '.join(f'{k}({v}次)' for k, v in people.items())}")
    if scenes:
        lines.append(f"- 提到的场景: {', '.join(f'{k}({v}次)' for k, v in scenes.items())}")
    lines.append("")

    # 互动表现
    lines.append(f"### 1.6 互动表现\n")
    interaction = target.get("interaction", {})
    if interaction.get("avg_read"):
        lines.append(f"- 平均阅读量: {interaction['avg_read']}")
        lines.append(f"- 最高阅读量: {interaction['max_read']}")
        lines.append(f"- 平均点赞数: {interaction['avg_like']}")
        lines.append("")

    # 历史文章清单
    lines.append(f"### 1.7 历史文章清单\n")
    lines.append("| 日期 | 标题 | 主题 | 阅读 | 点赞 |")
    lines.append("|------|------|------|------|------|")
    for a in target.get("article_list", []):
        topics_str = "/".join(a.get("topics", []))
        lines.append(
            f"| {a.get('create_date', '')} "
            f"| {a.get('title', '')} "
            f"| {topics_str} "
            f"| {a.get('read_count', 0)} "
            f"| {a.get('like_count', 0)} |"
        )
    lines.append("")

    # === 第二部分：参考账号 ===
    lines.append(f"## 二、参考账号分析\n")
    for ref in refs:
        lines.append(f"### {ref['name']}\n")
        lines.append(f"- 文章总数: {ref['total_articles']} 篇")

        ref_td = ref.get("topic_distribution", {})
        if ref_td:
            top3 = sorted(ref_td.items(), key=lambda x: x[1], reverse=True)[:3]
            lines.append(f"- 主要主题: {', '.join(f'{t}({c}篇)' for t, c in top3)}")

        ref_int = ref.get("interaction", {})
        if ref_int.get("avg_read"):
            lines.append(f"- 平均阅读量: {ref_int['avg_read']}")

        top_arts = ref_int.get("top_articles", [])
        if top_arts:
            lines.append(f"\n**Top 10 高互动文章:**\n")
            for i, a in enumerate(top_arts[:10], 1):
                lines.append(
                    f"{i}. 「{a['title']}」 "
                    f"阅读 {a.get('read_count', 0)} / 点赞 {a.get('like_count', 0)}"
                )
        lines.append("")

    # === 第三部分：建议 ===
    lines.append(f"## 三、建议的内容方向\n")
    recs = _build_recommendations(target, refs, config)
    for r in recs:
        lines.append(f"- {r}")
    lines.append("")

    # === 第四部分：栏目体系初版 ===
    lines.append(f"## 四、建议的栏目体系（初版，待确认）\n")
    columns = config.get("columns", [])
    if columns:
        lines.append("| 星期 | 栏目名称 | 内容方向 |")
        lines.append("|------|----------|----------|")
        weekday_names = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for col in columns:
            wd = col.get("weekday", 0)
            wd_name = weekday_names[wd] if wd < len(weekday_names) else f"第{wd}天"
            lines.append(f"| {wd_name} | {col['name']} | {col['focus']} |")
    lines.append("")

    lines.append("---\n")
    lines.append("**请审阅以上分析，确认后再进入内容规划阶段。**\n")
    lines.append("如需修正，可直接编辑 `output/analysis_report.json` 或反馈修正意见。\n")

    return "\n".join(lines)


# ------------------------------------------------------------------
# 入口函数
# ------------------------------------------------------------------

def run_analysis(config: dict, output_dir: Path, log_fn=None):
    """
    执行完整分析流程

    Args:
        config: target.json 配置内容
        output_dir: 输出根目录
        log_fn: 日志函数
    """
    _log = log_fn or (lambda msg: logger.info(msg))
    articles_dir = output_dir / "articles"

    # 1. 分析目标账号
    target_name = config["target"]["name"]
    target_file = articles_dir / f"{target_name}.json"
    if not target_file.exists():
        _log(f"未找到目标账号数据: {target_file}，请先运行 scrape 命令")
        return

    _log(f"分析目标账号: {target_name}")
    target_articles = json.loads(target_file.read_text(encoding="utf-8"))
    target_analysis = analyze_target(target_articles)

    # 2. 分析参考账号
    ref_analyses = []
    for ref in config.get("references", []):
        ref_name = ref["name"]
        ref_file = articles_dir / f"{ref_name}.json"
        if not ref_file.exists():
            _log(f"未找到参考账号数据: {ref_file}，跳过")
            continue

        _log(f"分析参考账号: {ref_name}")
        ref_articles = json.loads(ref_file.read_text(encoding="utf-8"))
        ref_analyses.append(analyze_reference(ref_articles, ref_name))

    # 3. 生成报告
    _log("生成综合分析报告...")
    json_path, md_path = generate_report(
        target_analysis, ref_analyses, config, output_dir
    )

    _log(f"\n分析完成！")
    _log(f"  可读报告: {md_path}")
    _log(f"  结构化数据: {json_path}")
    _log(f"\n请审阅 {md_path} 后确认，再运行 plan 命令生成日更规划。")
