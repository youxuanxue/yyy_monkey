const BASE = "http://127.0.0.1:17890";

function log(obj) {
  const el = document.getElementById("log");
  if (typeof obj === "string") el.textContent = obj;
  else el.textContent = JSON.stringify(obj, null, 2);
}

async function setLastTask(task) {
  await chrome.storage.local.set({ lastTask: task });
}

async function getLastTask() {
  const { lastTask } = await chrome.storage.local.get("lastTask");
  return lastTask || null;
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function extractCandidatesFromTab() {
  const tab = await getActiveTab();
  if (!tab?.id) throw new Error("No active tab");
  const res = await chrome.tabs.sendMessage(tab.id, { type: "EXTRACT_CANDIDATES" });
  return res?.items || [];
}

document.getElementById("btnHealth").addEventListener("click", async () => {
  const r = await fetch(`${BASE}/health`);
  log(await r.json());
});

document.getElementById("btnExtract").addEventListener("click", async () => {
  try {
    const items = await extractCandidatesFromTab();
    await chrome.storage.local.set({ lastCandidates: items });
    log({ extracted: items.length, sample: items.slice(0, 3) });
  } catch (e) {
    log({ error: String(e) });
  }
});

document.getElementById("btnReport").addEventListener("click", async () => {
  const runId = document.getElementById("runId").value.trim();
  if (!runId) return log("请先填写 run_id");
  const { lastCandidates } = await chrome.storage.local.get("lastCandidates");
  const items = Array.isArray(lastCandidates) ? lastCandidates : [];
  if (!items.length) return log("没有候选，请先点“提取候选”");

  const r = await fetch(`${BASE}/v1/candidates:batchUpsert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, items })
  });
  log(await r.json());
});

document.getElementById("btnNextTask").addEventListener("click", async () => {
  const r = await fetch(`${BASE}/v1/actionTasks:next`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id: "default" })
  });
  const data = await r.json();
  await setLastTask(data.task || null);
  log(data);
});

document.getElementById("btnOpenTask").addEventListener("click", async () => {
  const task = await getLastTask();
  if (!task) return log("没有 task，请先拉取任务");
  if (!task.candidate_url) return log({ error: "task 缺少 candidate_url", task });
  const tab = await chrome.tabs.create({ url: task.candidate_url });
  // 在页面加载完成后由 background 转发给 content script
  await chrome.storage.local.set({ pendingInject: { tabId: tab.id, task } });
  log({ opened: task.candidate_url, injected: "pending", task });
});

document.getElementById("btnReportOk").addEventListener("click", async () => {
  const task = await getLastTask();
  if (!task) return log("没有 task，请先拉取任务");
  const r = await fetch(`${BASE}/v1/actionTasks/${task.id}:report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "succeeded", error_message: null, evidence: null })
  });
  log(await r.json());
});

document.getElementById("btnReportFail").addEventListener("click", async () => {
  const task = await getLastTask();
  if (!task) return log("没有 task，请先拉取任务");
  const r = await fetch(`${BASE}/v1/actionTasks/${task.id}:report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "failed", error_message: "manual_fail", evidence: null })
  });
  log(await r.json());
});


