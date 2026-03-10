"""
微信公众号草稿发布工具

流程：
1. Playwright 打开 mp.weixin.qq.com 并登录
2. 读取 MD 文件，用类 Doocs 内联样式渲染为 HTML
3. 把 styled HTML 写入浏览器剪贴板（通过页内 execCommand('copy') trick）
4. 聚焦 ProseMirror，触发系统粘贴 (Meta+V)，ProseMirror 完美接管富文本
5. 点击存草稿
"""
import os
import re
import sys
import time
from pathlib import Path
import markdown
from bs4 import BeautifulSoup

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from media_publisher.core.browser import PlaywrightBrowser
from media_publisher.core.gzh import authenticate_gzh


# ─────────────────────────────────────────────
# 1. Markdown → 带内联样式的 HTML（类 Doocs 风格）
# ─────────────────────────────────────────────

# ── 配色方案：工程蓝图风 ──────────────────────────────────────────
#   主色：工程蓝 — CAD 蓝图色，工程人最熟悉，传达专业、可靠
#   强调：安全橙 — 安全帽/反光背心色，用于加粗文字，醒目但不刺眼
#   图标：📐 三角尺 — 连接工程制图与 PPT 排版，知性又贴切
BLUE = "#2B6CB0"         # 工程蓝（图纸/蓝图）
ORANGE = "#E8773A"       # 安全橙（安全帽/反光背心）
TEXT_COLOR = "#3f3f3f"   # 舒适深灰
_T = "background: transparent;"  # 强制透明，防 ProseMirror 灰块

H_ICON = "📐 "

TAG_STYLES: dict[str, str] = {
    "h1": (
        f"{_T} font-size: 1.6em; font-weight: bold; text-align: center;"
        " color: #1a1a1a; margin: 32px 0 20px; letter-spacing: 0.06em;"
    ),
    "h2": (
        f"font-size: 1.25em; font-weight: bold; color: #fff;"
        f" text-align: center; margin: 36px 0 16px; letter-spacing: 0.06em;"
        f" padding: 8px 16px; background: {BLUE}; border-radius: 6px;"
    ),
    "h3": (
        f"{_T} font-size: 1.1em; font-weight: bold; color: {BLUE};"
        " text-align: center; margin: 24px 0 12px; letter-spacing: 0.05em;"
    ),
    "h4": (
        f"{_T} font-size: 1em; font-weight: bold; color: {BLUE};"
        " text-align: center; margin: 18px 0 10px;"
    ),
    "p": (
        f"{_T} font-size: 16px; line-height: 2; color: {TEXT_COLOR};"
        " margin: 12px 0; letter-spacing: 0.05em;"
    ),
    "blockquote": (
        f"{_T} border-left: 4px solid {BLUE}; margin: 20px 0;"
        " padding: 10px 16px; color: #666; font-size: 15px;"
        " line-height: 1.9; font-style: italic;"
    ),
    "ul": (
        f"{_T} margin: 12px 0 12px 20px; padding-left: 20px;"
        f" list-style-type: disc; color: {TEXT_COLOR}; font-size: 16px; line-height: 2;"
    ),
    "ol": (
        f"{_T} margin: 12px 0 12px 20px; padding-left: 20px;"
        f" list-style-type: decimal; color: {TEXT_COLOR}; font-size: 16px; line-height: 2;"
    ),
    "li": f"{_T} margin-bottom: 10px; font-size: 16px; line-height: 2; color: {TEXT_COLOR};",
    "code": f"color: {ORANGE}; font-family: Consolas, 'Courier New', monospace; font-size: 14px;",
    "pre": (
        "background: #1e293b; border-radius: 8px; padding: 16px; margin: 16px 0;"
        " overflow-x: auto; font-size: 14px; line-height: 1.6;"
    ),
    "table": f"{_T} width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 15px;",
    "th": (
        f"border: 1px solid #dfe2e5; padding: 8px 14px;"
        f" font-weight: bold; color: #fff; background: {BLUE}; text-align: left;"
    ),
    "td": f"{_T} border: 1px solid #dfe2e5; padding: 8px 14px; color: {TEXT_COLOR};",
    "strong": f"font-weight: bold; color: {ORANGE};",
    "em": "font-style: italic; color: #888;",
    "a": f"color: {BLUE}; text-decoration: none;",
    "hr": f"{_T} border: none; border-top: 1px dashed #c0c8d0; margin: 28px 0;",
    "img": "max-width: 100%; height: auto; display: block; margin: 20px auto; border-radius: 6px;",
}


def render_wechat_html(md_text: str) -> str:
    """把 Markdown 渲染成微信公众号兼容的内联样式 HTML。"""
    raw_html = markdown.markdown(
        md_text,
        extensions=["extra", "tables", "fenced_code"],
    )
    soup = BeautifulSoup(raw_html, "html.parser")

    # 1. 为每个标签注入内联样式
    for tag, style in TAG_STYLES.items():
        for el in soup.find_all(tag):
            if tag == "code" and el.parent and el.parent.name == "pre":
                el["style"] = (
                    "color: #f8f8f2; font-family: Consolas, 'Courier New', monospace;"
                    " font-size: 14px;"
                )
            else:
                el["style"] = style

    # 2. 每个 h2/h3 标题前加图标
    for h in soup.find_all(["h2", "h3"]):
        h.insert(0, H_ICON)

    # 3. 不使用 wrapper <div>（ProseMirror 会把 div 转成带灰背景的 section）
    #    直接返回裸 HTML 片段，让 ProseMirror 逐个接管每个 <p>/<h2> 等块元素
    return str(soup)


# ─────────────────────────────────────────────
# 1.5 公众号名片指令提取
# ─────────────────────────────────────────────

PROFILE_CARD_RE = re.compile(r"<!--\s*公众号名片[：:]\s*(.+?)\s*-->")


def extract_profile_cards(md_text: str) -> tuple[str, list[str]]:
    """提取 <!-- 公众号名片：xxx --> 指令，替换为唯一占位符。

    Returns:
        (替换后的 markdown, [公众号名称, ...])
    """
    cards: list[str] = []

    def _repl(m: re.Match) -> str:
        name = m.group(1).strip()
        idx = len(cards)
        cards.append(name)
        return f"〔公众号名片占位{idx}〕"

    return PROFILE_CARD_RE.sub(_repl, md_text), cards


# ─────────────────────────────────────────────
# 2. 剪贴板写入 + 粘贴（核心技巧）
# ─────────────────────────────────────────────

# 用 execCommand('copy') 把 HTML 写入系统剪贴板，然后 Meta+V 粘贴进 ProseMirror
CLIPBOARD_JS = """
(html) => {
    // 在页面外创建一个不可见的 div，填入 HTML，选中，再复制
    const div = document.createElement('div');
    div.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0;';
    div.innerHTML = html;
    document.body.appendChild(div);

    const range = document.createRange();
    range.selectNodeContents(div);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);

    const ok = document.execCommand('copy');
    sel.removeAllRanges();
    document.body.removeChild(div);
    return ok;
}
"""


# ─────────────────────────────────────────────
# 3. 发布器
# ─────────────────────────────────────────────

class GzhDraftPublisher:
    BASE_URL = "https://mp.weixin.qq.com"

    def __init__(self, headless: bool = False):
        self.session = PlaywrightBrowser("gzh_article", None, headless, print)

    def start(self):
        self.session.start()

    def close(self):
        self.session.close()

    @property
    def page(self):
        return self.session.page

    def authenticate(self, timeout: int = 120):
        if not self.page:
            self.start()
        authenticate_gzh(
            page=self.page,
            base_url=self.BASE_URL,
            log_fn=print,
            save_fn=self.session.save_auth_state,
            timeout=timeout,
            has_stored_auth=self.session.has_stored_auth,
        )

    def _extract_token(self) -> str | None:
        url = self.page.url
        m = re.search(r"token=(\d+)", url)
        if m:
            return m.group(1)
        return self.page.evaluate(
            """() => {
                const links = document.querySelectorAll('a[href*="token="]');
                for (const a of links) {
                    const m = a.href.match(/token=(\\d+)/);
                    if (m) return m[1];
                }
                try {
                    if (window.wx?.commonData?.token)
                        return String(window.wx.commonData.token);
                } catch (_) {}
                return null;
            }"""
        )

    def _insert_profile_card(
        self, ep, account_name: str, placeholder: str
    ) -> bool:
        """通过微信编辑器 UI 在占位符位置插入公众号名片。

        步骤：
        1. 在 ProseMirror 中定位占位符文本并选中
        2. 删除占位符
        3. 点击工具栏「账号名片」
        4. 搜索公众号 → 选择 → 插入
        """
        # 0. 确保编辑器获得焦点
        ep.locator('.ProseMirror[contenteditable="true"]').first.click()
        time.sleep(0.3)

        # 1. 在编辑器中找到占位符文本并选中
        found = ep.evaluate(
            """(placeholder) => {
                const editor = document.querySelector(
                    '.ProseMirror[contenteditable="true"]'
                );
                if (!editor) return false;
                const walker = document.createTreeWalker(
                    editor, NodeFilter.SHOW_TEXT
                );
                let node;
                while ((node = walker.nextNode())) {
                    const idx = node.textContent.indexOf(placeholder);
                    if (idx !== -1) {
                        const range = document.createRange();
                        range.setStart(node, idx);
                        range.setEnd(node, idx + placeholder.length);
                        const sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        return true;
                    }
                }
                return false;
            }""",
            placeholder,
        )
        if not found:
            print(f"    ⚠️ 未找到占位符: {placeholder}")
            return False

        # 2. 删除占位符文本
        ep.keyboard.press("Backspace")
        time.sleep(0.5)

        # 3. 打开「账号名片」插入对话框
        #    该菜单项在 tpl_dropdown 下拉菜单内，需先让菜单可见
        ep.evaluate(
            """() => {
                const item = document.getElementById(
                    'js_editor_insertProfile'
                );
                if (!item) return;
                let el = item.parentElement;
                while (el && el !== document.body) {
                    if (el.classList.contains('tpl_dropdown')) {
                        el.dispatchEvent(
                            new MouseEvent('mouseenter', {bubbles: true})
                        );
                        el.classList.add('tpl_dropdown_show');
                        const menu = el.querySelector('.tpl_dropdown_menu');
                        if (menu) menu.style.display = 'block';
                        break;
                    }
                    el = el.parentElement;
                }
            }"""
        )
        time.sleep(0.5)

        try:
            ep.locator("#js_editor_insertProfile").click(timeout=2000)
        except Exception:
            ep.locator("#js_editor_insertProfile").click(force=True)
        time.sleep(1.5)

        # 4. 在弹窗中搜索公众号
        search_input = ep.locator(
            'input[placeholder*="账号名称"]'
        ).first
        search_input.wait_for(state="visible", timeout=5000)
        search_input.fill(account_name)
        time.sleep(0.3)

        # 5. 点击搜索按钮
        ep.locator(".weui-desktop-search__btn").first.click()
        time.sleep(2)

        # 6. 选择匹配的公众号
        result = ep.locator(
            f'.wx_profile_nickname_wrp:has-text("{account_name}")'
        ).first
        result.wait_for(state="visible", timeout=5000)
        result.click()
        time.sleep(0.5)

        # 7. 点击「插入」
        insert_btn = ep.locator(
            'button.weui-desktop-btn_primary:has-text("插入")'
        ).first
        insert_btn.wait_for(state="visible", timeout=3000)
        insert_btn.click()
        time.sleep(1.5)

        print(f"    ✅ 公众号名片已插入: {account_name}")
        return True

    def create_draft(self, title: str, markdown_content: str) -> bool:
        token = self._extract_token()
        if not token:
            print("  ⚠️  token 未找到，尝试重载首页...")
            self.page.goto(
                f"{self.BASE_URL}/cgi-bin/home?t=home/index&lang=zh_CN",
                timeout=60000,
            )
            self.page.wait_for_load_state("domcontentloaded")
            token = self._extract_token()
        if not token:
            print("  ❌  无法获取 token，跳过此篇")
            return False

        print(f"  token: {token}")
        draft_url = (
            f"{self.BASE_URL}/cgi-bin/appmsg"
            f"?t=media/appmsg_edit_v2&action=edit&isNew=1&type=10"
            f"&createType=0&token={token}&lang=zh_CN"
        )

        # 打开新 tab
        print("  打开新建图文页面...")
        with self.session.context.expect_page() as new_page_info:
            self.page.evaluate(f"window.open('{draft_url}', '_blank')")
        ep = new_page_info.value
        ep.wait_for_load_state("domcontentloaded")
        time.sleep(3)

        try:
            # ── 填写标题（textarea#title）────────────────────────────
            # 微信编辑器标题是 <textarea id="title">，不是 <input>
            print(f"  填写标题: {title[:40]}...")
            title_el = ep.locator("textarea#title").first
            title_el.wait_for(state="visible", timeout=15000)
            title_el.click()
            time.sleep(0.2)
            ep.keyboard.press("Meta+A")
            ep.keyboard.type(title, delay=20)
            print("  ✅ 标题写入")

            # ── 填写作者 ──────────────────────────────────────────────
            # 🪛 螺丝刀：图标匹配账号名，土木工程师人设，接地气又有辨识度
            try:
                author_el = ep.locator("input#author").first
                if author_el.is_visible(timeout=3000):
                    author_el.click()
                    time.sleep(0.2)
                    ep.keyboard.press("Meta+A")
                    ep.keyboard.type("🪛螺丝刀", delay=20)
                    print("  ✅ 作者写入")
            except Exception:
                pass

            # ── 提取公众号名片指令 ────────────────────────────────────
            content_for_render, profile_cards = extract_profile_cards(
                markdown_content
            )

            # ── 渲染 Markdown ──────────────────────────────────────────
            styled_html = render_wechat_html(content_for_render)

            # ── 把 styled HTML 写入剪贴板 ─────────────────────────────
            print("  将 HTML 写入剪贴板...")
            copied = ep.evaluate(CLIPBOARD_JS, styled_html)
            print(f"  剪贴板写入: {'✅' if copied else '⚠️ execCommand 返回 false'}")

            # ── 聚焦 ProseMirror，清空，然后粘贴 ──────────────────────
            print("  聚焦编辑器并粘贴...")
            editor_sel = '.ProseMirror[contenteditable="true"]'

            # 等待编辑器出现
            ep.wait_for_selector(editor_sel, timeout=15000)
            editor = ep.locator(editor_sel).first

            editor.click()
            time.sleep(0.5)

            # 全选清空（编辑器初始只有一个空 <section>，删干净）
            ep.keyboard.press("Meta+A")
            ep.keyboard.press("Backspace")
            time.sleep(0.3)

            # 粘贴 → 触发 ProseMirror 内置的 paste handler，完美保留富文本
            ep.keyboard.press("Meta+V")
            time.sleep(1.5)
            print("  ✅ 内容已粘贴")

            # ── 插入公众号名片 ────────────────────────────────────────
            if profile_cards:
                print(f"  📇 插入 {len(profile_cards)} 个公众号名片...")
                for idx, name in enumerate(profile_cards):
                    placeholder = f"〔公众号名片占位{idx}〕"
                    self._insert_profile_card(ep, name, placeholder)

            # ── 点击存草稿 ────────────────────────────────────────────
            time.sleep(1)
            print("  点击「存草稿」...")
            # 先用 JS 找到包含「存草稿」文字的按钮并点击
            saved = ep.evaluate(
                """() => {
                    // 遍历所有 button，找到文本含「存草稿」的
                    for (const btn of document.querySelectorAll('button, a, span')) {
                        const txt = (btn.textContent || '').trim();
                        if (txt === '存草稿' || txt.includes('存草稿')) {
                            btn.click();
                            return btn.tagName + ':' + txt;
                        }
                    }
                    return null;
                }"""
            )
            if saved:
                print(f"  ✅ 存草稿按钮已点击 ({saved})")
            else:
                # 兜底：Playwright locator（宽松匹配）
                for sel in [
                    'button:text("存草稿")',
                    'button:has-text("草稿")',
                    ".js_save_draft",
                    "#js_save",
                ]:
                    try:
                        btn = ep.locator(sel).first
                        if btn.count() > 0 and btn.is_visible(timeout=1500):
                            btn.click()
                            saved = True
                            print(f"  ✅ 存草稿按钮已点击 ({sel})")
                            break
                    except Exception:
                        pass
                if not saved:
                    print("  ⚠️ 未找到存草稿按钮，页面将在关闭时丢失")

            time.sleep(3)
            return True

        except Exception as e:
            print(f"  ❌ 出错: {e}")
            return False
        finally:
            ep.close()
            time.sleep(1)


# ─────────────────────────────────────────────
# 4. 主流程
# ─────────────────────────────────────────────

def main():
    content_dir = Path(
        "/Users/xuejiao/Desktop/History/inspur/cowork/transcript/ppt_gen/content-series"
    )
    if not content_dir.exists():
        print(f"❌ 目录不存在: {content_dir}")
        return

    md_files = sorted(content_dir.glob("*.md"))
    if not md_files:
        print("❌ 没有找到 .md 文件")
        return

    # ── 控制参数 ──────────────────────────────────────────────────
    SKIP = 0           # 跳过前 N 篇（已发布的）
    files_to_run = md_files[SKIP:]
    total = len(files_to_run)
    print(f"找到 {len(md_files)} 个文件，跳过前 {SKIP} 篇，本次处理 {total} 篇\n")

    pub = GzhDraftPublisher(headless=False)
    try:
        pub.authenticate()

        for i, md_file in enumerate(files_to_run, 1):
            print(f"\n[{i}/{total}] {md_file.name}")
            content = md_file.read_text(encoding="utf-8")

            # 提取一级标题作为文章标题，正文中去掉该行
            title = md_file.stem
            m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if m:
                title = m.group(1).strip()
                content = content.replace(m.group(0), "", 1).strip()

            pub.create_draft(title=title, markdown_content=content)

            if i < total:
                print("  等待 4 秒...")
                time.sleep(4)

    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback; traceback.print_exc()
    finally:
        pub.close()


if __name__ == "__main__":
    main()
