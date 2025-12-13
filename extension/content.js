// MVP：站点适配（抖音精选分栏页优先，比如 /jingxuan/child）。
// 说明：
// - 抖音页面结构可能频繁变化；这里用“尽量稳健的启发式提取”。
// - 只提取当前页面可见的公开信息（标题/作者/时长/热度等若可得）。

function uniqBy(arr, keyFn) {
  const seen = new Set();
  const out = [];
  for (const x of arr) {
    const k = keyFn(x);
    if (!k || seen.has(k)) continue;
    seen.add(k);
    out.push(x);
  }
  return out;
}

function getUrlObj(href) {
  try {
    return new URL(href, location.href);
  } catch {
    return null;
  }
}

function pickText(el) {
  if (!el) return null;
  const t = (el.textContent || "").replace(/\s+/g, " ").trim();
  return t || null;
}

function extractFromDouyinJingxuan() {
  // 1) 优先找包含 modal_id 的链接（精选页经常用 modal 打开详情）
  const anchors = Array.from(document.querySelectorAll("a[href*='modal_id=']"));
  const cards = anchors
    .map((a) => {
      const u = getUrlObj(a.getAttribute("href"));
      if (!u) return null;
      const modalId = u.searchParams.get("modal_id");
      if (!modalId) return null;

      // card 容器（启发式：向上找一个较大的块）
      const container = a.closest("li, article, div") || a.parentElement;
      const title =
        pickText(container?.querySelector("h1, h2, h3")) ||
        pickText(container?.querySelector("[class*='title' i]")) ||
        pickText(container);

      // 作者（页面上一般是 @xxx）
      const author =
        pickText(container?.querySelector("[class*='author' i]")) ||
        (() => {
          const t = pickText(container);
          if (!t) return null;
          const m = t.match(/@([^\s·]{1,30})/);
          return m ? `@${m[1]}` : null;
        })();

      // 时长（如 04:29）
      const dur =
        (() => {
          const t = pickText(container);
          if (!t) return null;
          const m = t.match(/\b(\d{1,2}:\d{2})\b/);
          return m ? m[1] : null;
        })();

      // 热度/播放/点赞等数字（页面上可能只是一个数字，先尽量取）
      const heat =
        (() => {
          const t = pickText(container);
          if (!t) return null;
          const m = t.match(/\b(\d+(\.\d+)?万|\d+)\b/);
          return m ? m[1] : null;
        })();

      const canonical = new URL(location.href);
      canonical.searchParams.set("modal_id", modalId);

      return {
        source: "search",
        url: canonical.toString(),
        video_id: modalId,
        author_name: author,
        title: title,
        raw_text: null,
        evidence: null,
        extra: { duration: dur, heat }
      };
    })
    .filter(Boolean);

  return uniqBy(cards, (x) => x.url).slice(0, 50);
}

function extractGenericLinks() {
  const links = Array.from(document.querySelectorAll("a[href]"))
    .map((a) => a.href)
    .filter((h) => typeof h === "string" && h.startsWith("http"));

  const urlItems = uniqBy(links, (x) => x).slice(0, 50);
  return urlItems.map((url) => ({
    source: "search",
    url,
    video_id: null,
    author_name: null,
    title: document.title || null,
    raw_text: null,
    evidence: null
  }));
}

function extractCandidates() {
  const isDouyinJingxuan = location.hostname.includes("douyin.com") && location.pathname.startsWith("/jingxuan/");
  if (isDouyinJingxuan) {
    const items = extractFromDouyinJingxuan();
    if (items.length) return items;
  }
  return extractGenericLinks();
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "EXTRACT_CANDIDATES") {
    try {
      const items = extractCandidates();
      sendResponse({ items });
    } catch (e) {
      sendResponse({ items: [], error: String(e) });
    }
  }
  if (msg?.type === "SHOW_TASK_OVERLAY") {
    try {
      showTaskOverlay(msg.task);
      sendResponse({ ok: true });
    } catch (e) {
      sendResponse({ ok: false, error: String(e) });
    }
  }
  return true;
});

function findCommentInput() {
  // 启发式：找 textarea 或 contenteditable
  const ta = document.querySelector("textarea");
  if (ta) return { el: ta, kind: "textarea" };
  const ce = document.querySelector("[contenteditable='true']");
  if (ce) return { el: ce, kind: "contenteditable" };
  return null;
}

function setInputValue(target, text) {
  if (!target) return false;
  const { el, kind } = target;
  if (kind === "textarea") {
    el.focus();
    el.value = text;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
  if (kind === "contenteditable") {
    el.focus();
    el.textContent = text;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }
  return false;
}

function showTaskOverlay(task) {
  // 只在 douyin.com 上显示（避免污染其他站点）
  if (!location.hostname.includes("douyin.com")) return;

  const old = document.getElementById("yyy-monkey-overlay");
  if (old) old.remove();

  const wrap = document.createElement("div");
  wrap.id = "yyy-monkey-overlay";
  wrap.style.position = "fixed";
  wrap.style.top = "12px";
  wrap.style.right = "12px";
  wrap.style.width = "360px";
  wrap.style.zIndex = "2147483647";
  wrap.style.background = "white";
  wrap.style.border = "1px solid rgba(0,0,0,0.12)";
  wrap.style.boxShadow = "0 8px 24px rgba(0,0,0,0.15)";
  wrap.style.borderRadius = "10px";
  wrap.style.fontFamily = "ui-sans-serif, system-ui";
  wrap.style.padding = "10px";

  const title = document.createElement("div");
  title.textContent = "yyy_monkey 任务面板（手动发布）";
  title.style.fontWeight = "600";
  title.style.marginBottom = "8px";

  const meta = document.createElement("div");
  meta.style.fontSize = "12px";
  meta.style.color = "#555";
  meta.style.marginBottom = "8px";
  meta.textContent = `task=${task?.id || "-"} type=${task?.action_type || "-"}`;

  const txt = document.createElement("textarea");
  txt.style.width = "100%";
  txt.style.height = "90px";
  txt.style.boxSizing = "border-box";
  txt.style.padding = "8px";
  txt.value = task?.payload?.comment_text || "";

  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.gap = "8px";
  row.style.marginTop = "8px";

  const btnFill = document.createElement("button");
  btnFill.textContent = "一键填入输入框";
  btnFill.style.flex = "1";
  btnFill.onclick = () => {
    const ok = setInputValue(findCommentInput(), txt.value);
    hint.textContent = ok
      ? "已填入输入框。请你手动点击“发布”，再回到插件回报结果。"
      : "未找到评论输入框（页面结构可能变化）。你可先复制后手动粘贴。";
  };

  const btnCopy = document.createElement("button");
  btnCopy.textContent = "复制";
  btnCopy.style.width = "88px";
  btnCopy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(txt.value);
      hint.textContent = "已复制。请粘贴到评论框并手动发布，然后回到插件回报结果。";
    } catch (e) {
      hint.textContent = `复制失败：${String(e)}`;
    }
  };

  row.appendChild(btnFill);
  row.appendChild(btnCopy);

  const hint = document.createElement("div");
  hint.style.marginTop = "8px";
  hint.style.fontSize = "12px";
  hint.style.color = "#666";
  hint.textContent = "说明：出于合规与可控性，不提供自动点击“发布”。";

  const btnClose = document.createElement("button");
  btnClose.textContent = "关闭";
  btnClose.style.marginTop = "8px";
  btnClose.style.width = "100%";
  btnClose.onclick = () => wrap.remove();

  wrap.appendChild(title);
  wrap.appendChild(meta);
  wrap.appendChild(txt);
  wrap.appendChild(row);
  wrap.appendChild(hint);
  wrap.appendChild(btnClose);
  document.documentElement.appendChild(wrap);
}


