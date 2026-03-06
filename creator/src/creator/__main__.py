"""
公众号内容规划工具 CLI

用法:
    python -m creator scrape      # 抓取目标+参考公众号文章数据
    python -m creator analyze     # 分析数据并生成报告（需先 scrape）
    python -m creator plan        # 生成日更规划（需先 analyze 并人工确认）
    python -m creator run         # 一键执行 scrape + analyze（到人工确认节点暂停）
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "target.json"
OUTPUT_DIR = PROJECT_ROOT / "output"


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        console.print(f"[red]配置文件不存在: {CONFIG_PATH}[/red]")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _log(msg: str):
    console.print(msg)


def cmd_scrape(args):
    """抓取公众号文章数据"""
    from .scraper import GzhScraper

    config = _load_config()

    console.print(Panel("公众号文章抓取", style="bold blue"))
    console.print(f"目标账号: [bold]{config['target']['name']}[/bold]")
    refs = [r["name"] for r in config.get("references", [])]
    console.print(f"参考账号: {', '.join(refs)}")
    console.print()

    with GzhScraper(headless=args.headless, log_fn=_log) as scraper:
        scraper.authenticate(timeout=args.timeout)
        scraper.scrape_all(config, OUTPUT_DIR)

    console.print(Panel(
        f"抓取完成！数据保存在 {OUTPUT_DIR / 'articles'}",
        style="bold green",
    ))


def cmd_analyze(args):
    """分析数据并生成报告"""
    from .analyzer import run_analysis

    config = _load_config()

    console.print(Panel("内容分析", style="bold blue"))
    run_analysis(config, OUTPUT_DIR, log_fn=_log)

    report_path = OUTPUT_DIR / "analysis_report.md"
    if report_path.exists():
        console.print()
        console.print(Panel(
            f"[bold green]分析完成！[/bold green]\n\n"
            f"请审阅分析报告:\n"
            f"  {report_path}\n\n"
            f"确认无误后，运行 [bold]python -m creator plan[/bold] 生成日更规划。\n"
            f"如需修改，可编辑 {OUTPUT_DIR / 'analysis_report.json'}",
            title="人工确认节点",
            style="yellow",
        ))


def cmd_plan(args):
    """生成日更内容规划"""
    from .planner import generate_plan

    config = _load_config()
    analysis_path = OUTPUT_DIR / "analysis_report.json"

    if not analysis_path.exists():
        console.print("[red]未找到分析报告，请先运行 analyze 命令[/red]")
        sys.exit(1)

    console.print(Panel("日更规划生成", style="bold blue"))

    # 确认提示
    if not args.yes:
        console.print(f"分析报告: {analysis_path}")
        console.print("确认已审阅分析报告？", end=" ")
        confirm = input("[y/N] ").strip().lower()
        if confirm != "y":
            console.print("已取消。请先审阅分析报告后再运行。")
            return

    generate_plan(config, analysis_path, OUTPUT_DIR, log_fn=_log)


def cmd_run(args):
    """一键执行 scrape + analyze（到人工确认节点暂停）"""
    console.print(Panel("一键执行: 抓取 + 分析", style="bold blue"))

    # scrape
    cmd_scrape(args)
    console.print()

    # analyze
    cmd_analyze(args)


def main():
    parser = argparse.ArgumentParser(
        prog="creator",
        description="公众号内容规划工具 - 抓取、分析、生成日更规划",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="详细日志输出"
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # scrape
    p_scrape = subparsers.add_parser("scrape", help="抓取公众号文章数据")
    p_scrape.add_argument(
        "--headless", action="store_true", help="无头模式（不显示浏览器窗口）"
    )
    p_scrape.add_argument(
        "--timeout", type=int, default=120, help="等待扫码登录超时秒数"
    )

    # analyze
    subparsers.add_parser("analyze", help="分析数据并生成报告")

    # plan
    p_plan = subparsers.add_parser("plan", help="生成日更内容规划")
    p_plan.add_argument(
        "-y", "--yes", action="store_true", help="跳过确认直接生成"
    )

    # run
    p_run = subparsers.add_parser("run", help="一键执行 scrape + analyze")
    p_run.add_argument(
        "--headless", action="store_true", help="无头模式"
    )
    p_run.add_argument(
        "--timeout", type=int, default=120, help="等待扫码登录超时秒数"
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        return

    commands = {
        "scrape": cmd_scrape,
        "analyze": cmd_analyze,
        "plan": cmd_plan,
        "run": cmd_run,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
