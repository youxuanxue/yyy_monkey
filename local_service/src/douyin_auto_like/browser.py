from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import shutil

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


@dataclass(frozen=True)
class ChromeConfig:
    profile_dir: Path
    headless: bool = False
    window_width: int = 1280
    window_height: int = 900


def _detect_chromedriver_path() -> Optional[str]:
    # 优先使用本机已安装 chromedriver，避免 Selenium Manager 偶发卡住/网络问题
    p = shutil.which("chromedriver")
    if p:
        return p
    for candidate in ("/opt/homebrew/bin/chromedriver", "/usr/local/bin/chromedriver"):
        if Path(candidate).exists():
            return candidate
    return None


def build_chrome_driver(cfg: ChromeConfig) -> webdriver.Chrome:
    """
    使用 Chrome Profile 复用登录态；依赖 Selenium 4 的 Selenium Manager 自动寻找/下载 driver。
    """
    cfg.profile_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument(f"--user-data-dir={str(cfg.profile_dir)}")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=zh-CN")
    options.add_argument(f"--window-size={cfg.window_width},{cfg.window_height}")

    if cfg.headless:
        # 新版无头更接近真实 Chrome；但首次扫码登录不建议开无头
        options.add_argument("--headless=new")

    chromedriver_path = _detect_chromedriver_path()
    if chromedriver_path:
        print(f"[douyin-like] 使用本机 chromedriver：{chromedriver_path}", flush=True)
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(options=options, service=service)
    else:
        print("[douyin-like] 未检测到本机 chromedriver，将尝试 Selenium Manager（可能会卡住）", flush=True)
        driver = webdriver.Chrome(options=options)
    return driver


def safe_quit(driver: Optional[webdriver.Chrome]) -> None:
    try:
        if driver is not None:
            driver.quit()
    except Exception:
        # 避免退出时影响主流程
        pass


