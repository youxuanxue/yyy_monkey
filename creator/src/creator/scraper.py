"""
微信公众号文章抓取器

通过 Playwright 登录 mp.weixin.qq.com，利用内部 AJAX 接口获取公众号文章列表和互动数据。
支持两种抓取模式：
- 深度抓取（目标账号）：获取全部文章 + 正文内容 + 互动数据
- 列表抓取（参考账号）：获取近期文章列表 + 采样互动数据
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from playwright.sync_api import sync_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)

AUTH_DIR = Path.home() / ".media-publisher"
AUTH_FILE = AUTH_DIR / "gzh_auth.json"


class GzhScraper:
    """微信公众号文章抓取器"""

    BASE_URL = "https://mp.weixin.qq.com"

    def __init__(
        self,
        headless: bool = False,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.headless = headless
        self._log_fn = log_fn or (lambda msg: logger.info(msg))
        self._playwright = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._token: Optional[str] = None

    def _log(self, msg: str):
        self._log_fn(msg)

    # ------------------------------------------------------------------
    # 浏览器生命周期
    # ------------------------------------------------------------------

    def start(self):
        """启动浏览器并加载认证状态"""
        self._log("正在启动浏览器...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--start-maximized"],
        )

        if AUTH_FILE.exists():
            self._log(f"加载登录状态: {AUTH_FILE}")
            self._context = self._browser.new_context(
                storage_state=str(AUTH_FILE),
                no_viewport=True,
            )
        else:
            self._log("未找到登录状态，需要扫码登录")
            AUTH_DIR.mkdir(parents=True, exist_ok=True)
            self._context = self._browser.new_context(no_viewport=True)

        self._page = self._context.new_page()

    def close(self):
        """关闭浏览器"""
        if self._context:
            try:
                self._context.storage_state(path=str(AUTH_FILE))
                self._log(f"登录状态已保存: {AUTH_FILE}")
            except Exception as e:
                self._log(f"保存登录状态失败: {e}")
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._log("浏览器已关闭")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # 登录与 token 获取
    # ------------------------------------------------------------------

    def authenticate(self, timeout: int = 120):
        """登录 mp.weixin.qq.com 并提取 token"""
        self._log("正在打开微信公众号后台...")
        self._page.goto(self.BASE_URL, timeout=60000)
        self._page.wait_for_load_state("domcontentloaded")

        logged_in_selector = ".new-creation__menu, .weui-desktop-layout__main"

        if AUTH_FILE.exists():
            try:
                if self._page.locator(logged_in_selector).first.is_visible(timeout=5000):
                    self._log("已登录")
                    self._extract_token()
                    return
            except Exception:
                pass

        self._log("请在浏览器中扫码登录微信公众号...")
        try:
            self._page.wait_for_selector(
                logged_in_selector, state="visible", timeout=timeout * 1000
            )
            self._log("登录成功！")
            self._context.storage_state(path=str(AUTH_FILE))
        except Exception as e:
            raise RuntimeError(f"等待扫码登录超时（{timeout}秒），请重试") from e

        self._extract_token()

    def _extract_token(self):
        """从当前页面 URL 中提取 token"""
        url = self._page.url
        match = re.search(r"token=(\d+)", url)
        if match:
            self._token = match.group(1)
            self._log(f"已获取 token: {self._token}")
            return

        # 尝试导航到首页获取 token
        self._page.goto(f"{self.BASE_URL}/cgi-bin/home?lang=zh_CN", timeout=30000)
        self._page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        url = self._page.url
        match = re.search(r"token=(\d+)", url)
        if match:
            self._token = match.group(1)
            self._log(f"已获取 token: {self._token}")
        else:
            raise RuntimeError(f"无法从 URL 中提取 token: {url}")

    # ------------------------------------------------------------------
    # 内部 API 调用
    # ------------------------------------------------------------------

    def _api_get(self, path: str, params: dict) -> dict:
        """通过 page.evaluate 发起内部 API 请求"""
        params["token"] = self._token
        params["lang"] = "zh_CN"
        params["f"] = "json"
        params["ajax"] = "1"

        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.BASE_URL}{path}?{query}"

        result = self._page.evaluate(
            """async (url) => {
                const resp = await fetch(url, { credentials: 'include' });
                return await resp.json();
            }""",
            url,
        )
        return result

    def search_account(self, name: str) -> Optional[dict]:
        """
        搜索公众号，返回第一个匹配的账号信息（含 fakeid）

        Returns:
            {"fakeid": str, "nickname": str, "alias": str, "round_head_img": str}
            或 None（未找到）
        """
        self._log(f"搜索公众号: {name}")
        data = self._api_get("/cgi-bin/searchbiz", {
            "action": "search_biz",
            "begin": "0",
            "count": "5",
            "query": name,
        })

        biz_list = data.get("list", [])
        if not biz_list:
            self._log(f"未找到公众号: {name}")
            return None

        # 优先精确匹配
        for biz in biz_list:
            if biz.get("nickname") == name:
                self._log(f"找到公众号: {biz['nickname']} (fakeid={biz['fakeid']})")
                return biz

        # 取第一个结果
        biz = biz_list[0]
        self._log(f"找到公众号（模糊匹配）: {biz['nickname']} (fakeid={biz['fakeid']})")
        return biz

    def get_article_list(
        self, fakeid: str, count: int = 10, max_pages: int = 50
    ) -> list[dict]:
        """
        获取公众号文章列表（分页获取）

        Args:
            fakeid: 公众号的 fakeid
            count: 每页数量（最大 10）
            max_pages: 最大翻页数

        Returns:
            文章列表，每篇含 aid, title, digest, link, create_time, cover 等
        """
        all_articles = []
        begin = 0

        for page_num in range(max_pages):
            self._log(f"  获取文章列表 第{page_num + 1}页 (begin={begin})...")
            data = self._api_get("/cgi-bin/appmsg", {
                "action": "list_ex",
                "begin": str(begin),
                "count": str(count),
                "fakeid": fakeid,
                "type": "9",
                "query": "",
            })

            articles = data.get("app_msg_list", [])
            if not articles:
                break

            all_articles.extend(articles)
            total = data.get("app_msg_cnt", 0)
            self._log(f"  获取 {len(articles)} 篇 (累计 {len(all_articles)}/{total})")

            if len(all_articles) >= total:
                break

            begin += count
            time.sleep(1.5)  # 请求间隔，避免频率限制

        return all_articles

    def get_article_content(self, url: str) -> dict:
        """
        访问文章页面，提取正文内容和互动数据

        Returns:
            {"content": str, "read_count": int, "like_count": int}
        """
        page = self._context.new_page()
        result = {"content": "", "read_count": 0, "like_count": 0}

        try:
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)

            # 提取正文
            content = page.evaluate(
                """() => {
                    const el = document.querySelector('#js_content');
                    return el ? el.innerText : '';
                }"""
            )
            result["content"] = (content or "").strip()

            # 提取阅读量（可能需要滚动到底部触发加载）
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

            read_count = page.evaluate(
                """() => {
                    const el = document.querySelector('#js_read_area .read_num, .read_num_text');
                    if (el) {
                        const m = el.textContent.match(/\\d+/);
                        return m ? parseInt(m[0]) : 0;
                    }
                    return 0;
                }"""
            )
            result["read_count"] = read_count or 0

            like_count = page.evaluate(
                """() => {
                    // "在看" 或 "点赞" 数量
                    const selectors = [
                        '#js_like_area .like_num',
                        '.like_num_text',
                        '#js_read_like_area .like_num',
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const m = el.textContent.match(/\\d+/);
                            if (m) return parseInt(m[0]);
                        }
                    }
                    return 0;
                }"""
            )
            result["like_count"] = like_count or 0

        except Exception as e:
            self._log(f"  获取文章内容失败: {e}")
        finally:
            page.close()

        return result

    # ------------------------------------------------------------------
    # 高级抓取流程
    # ------------------------------------------------------------------

    def scrape_account_deep(self, name: str, output_dir: Path) -> Optional[Path]:
        """
        深度抓取目标账号：全部文章 + 正文 + 互动数据

        Args:
            name: 公众号名称
            output_dir: 输出目录

        Returns:
            输出文件路径
        """
        account = self.search_account(name)
        if not account:
            return None

        self._log(f"\n=== 深度抓取: {name} ===")
        articles = self.get_article_list(account["fakeid"], count=10)
        self._log(f"共 {len(articles)} 篇文章，开始逐篇获取正文和互动数据...")

        results = []
        for i, art in enumerate(articles):
            self._log(f"  [{i + 1}/{len(articles)}] {art.get('title', '无标题')}")
            detail = self.get_article_content(art.get("link", ""))
            results.append({
                "title": art.get("title", ""),
                "digest": art.get("digest", ""),
                "link": art.get("link", ""),
                "cover": art.get("cover", ""),
                "create_time": art.get("create_time", 0),
                "create_date": _ts_to_date(art.get("create_time", 0)),
                "content": detail["content"],
                "read_count": detail["read_count"],
                "like_count": detail["like_count"],
            })
            time.sleep(2)

        output_file = output_dir / f"{name}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._log(f"已保存 {len(results)} 篇文章到 {output_file}")
        return output_file

    def scrape_account_list(
        self,
        name: str,
        output_dir: Path,
        max_articles: int = 60,
        sample_detail: int = 20,
    ) -> Optional[Path]:
        """
        列表抓取参考账号：文章列表 + 采样互动数据

        Args:
            name: 公众号名称
            output_dir: 输出目录
            max_articles: 最大获取文章数
            sample_detail: 采样获取互动数据的文章数

        Returns:
            输出文件路径
        """
        account = self.search_account(name)
        if not account:
            return None

        self._log(f"\n=== 列表抓取: {name} ===")
        max_pages = (max_articles + 9) // 10
        articles = self.get_article_list(
            account["fakeid"], count=10, max_pages=max_pages
        )
        articles = articles[:max_articles]
        self._log(f"获取 {len(articles)} 篇文章标题")

        results = []
        for i, art in enumerate(articles):
            entry = {
                "title": art.get("title", ""),
                "digest": art.get("digest", ""),
                "link": art.get("link", ""),
                "cover": art.get("cover", ""),
                "create_time": art.get("create_time", 0),
                "create_date": _ts_to_date(art.get("create_time", 0)),
                "read_count": 0,
                "like_count": 0,
            }

            if i < sample_detail:
                self._log(
                    f"  [{i + 1}/{min(len(articles), sample_detail)}] "
                    f"获取互动数据: {art.get('title', '无标题')[:30]}..."
                )
                detail = self.get_article_content(art.get("link", ""))
                entry["read_count"] = detail["read_count"]
                entry["like_count"] = detail["like_count"]
                time.sleep(2)

            results.append(entry)

        output_file = output_dir / f"{name}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._log(f"已保存 {len(results)} 篇文章到 {output_file}")
        return output_file

    def scrape_all(self, config: dict, output_dir: Path):
        """
        根据配置执行完整抓取流程

        Args:
            config: target.json 配置内容
            output_dir: 输出根目录
        """
        articles_dir = output_dir / "articles"
        articles_dir.mkdir(parents=True, exist_ok=True)

        # 1. 深度抓取目标账号
        target_name = config["target"]["name"]
        self._log(f"\n{'='*50}")
        self._log(f"开始深度抓取目标账号: {target_name}")
        self._log(f"{'='*50}")
        self.scrape_account_deep(target_name, articles_dir)

        # 2. 列表抓取参考账号
        for ref in config.get("references", []):
            ref_name = ref["name"]
            self._log(f"\n{'='*50}")
            self._log(f"开始列表抓取参考账号: {ref_name}")
            self._log(f"{'='*50}")
            self.scrape_account_list(ref_name, articles_dir)

        self._log(f"\n全部抓取完成，数据保存在 {articles_dir}")


def _ts_to_date(ts: int) -> str:
    """Unix 时间戳转日期字符串"""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        return ""
