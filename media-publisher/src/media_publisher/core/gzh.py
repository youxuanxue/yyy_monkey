import time
from playwright.sync_api import Page
from typing import Callable

def authenticate_gzh(
    page: Page,
    base_url: str,
    log_fn: Callable[[str], None],
    save_fn: Callable[[], None],
    timeout: int = 120,
    has_stored_auth: bool = False,
):
    """
    微信公众号 (mp.weixin.qq.com) 扫码登录逻辑
    """
    log_fn("正在打开微信公众号后台...")
    page.goto(base_url, timeout=60000)
    page.wait_for_load_state("domcontentloaded")

    logged_in_selector = ".new-creation__menu, .weui-desktop-layout__main"

    if has_stored_auth:
        try:
            if page.locator(logged_in_selector).first.is_visible(timeout=5000):
                log_fn("已登录")
                return
        except Exception:
            pass

    log_fn("请在浏览器中扫码登录微信公众号...")
    try:
        page.wait_for_selector(
            logged_in_selector, state="visible", timeout=timeout * 1000
        )
        log_fn("登录成功！")
        save_fn()
    except Exception as e:
        raise RuntimeError(f"等待扫码登录超时（{timeout}秒），请重试") from e
