// MVP: 负责把 popup 里的“待注入任务”在页面加载完成后转发给 content script
chrome.runtime.onInstalled.addListener(() => {});

async function tryInjectOnTab(tabId) {
  const { pendingInject } = await chrome.storage.local.get("pendingInject");
  if (!pendingInject) return;
  if (pendingInject.tabId !== tabId) return;

  try {
    await chrome.tabs.sendMessage(tabId, { type: "SHOW_TASK_OVERLAY", task: pendingInject.task });
    await chrome.storage.local.remove("pendingInject");
  } catch (e) {
    // content script 可能还没 ready，交给下一次 onUpdated 再试
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "complete") {
    tryInjectOnTab(tabId);
  }
});


