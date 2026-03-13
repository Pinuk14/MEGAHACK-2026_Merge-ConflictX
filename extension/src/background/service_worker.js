// Handles communication between popup and content script
let autoAnalyzeEnabled = false;

chrome.storage.local.get(["autoAnalyzeEnabled"], (result) => {
  if (typeof result.autoAnalyzeEnabled === "boolean") {
    autoAnalyzeEnabled = result.autoAnalyzeEnabled;
  }
});

async function analyzeTab(tabId) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, { action: "extractPageContent" }, async (response) => {
      if (chrome.runtime.lastError || !response || response.error) {
        console.warn("Auto analyze failed:", response?.error || chrome.runtime.lastError?.message);
        resolve();
        return;
      }

      try {
        const hash = btoa(unescape(encodeURIComponent(response.data.metadata.url + response.data.metadata.title)));
        await fetch("http://localhost:8000/analyze_page", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...response.data, page_hash: hash })
        });
      } catch (err) {
        console.warn("Auto analyze API error:", err.message);
      }

      resolve();
    });
  });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!autoAnalyzeEnabled) return;
  if (changeInfo.status !== "complete") return;
  if (!tab?.url || !tab.url.startsWith("http")) return;
  analyzeTab(tabId);
});
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "scrapeAndAnalyze") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs[0].id;
      chrome.tabs.sendMessage(tabId, { action: "extractPageContent" }, async (response) => {
        if (chrome.runtime.lastError || !response || response.error) {
          sendResponse({ error: response?.error || "Failed to scrape page." });
          return;
        }
        // Caching: generate hash
        const hash = btoa(unescape(encodeURIComponent(response.data.metadata.url + response.data.metadata.title)));
        // Send to backend
        try {
          const apiResponse = await fetch("http://localhost:8000/analyze_page", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...response.data, page_hash: hash })
          });
          if (!apiResponse.ok) throw new Error("API request failed");
          const result = await apiResponse.json();
          sendResponse({ summary: result.summary });
        } catch (err) {
          sendResponse({ error: "API error: " + err.message });
        }
      });
    });
    return true;
  }

  if (request.action === "setAutoAnalyze") {
    autoAnalyzeEnabled = Boolean(request.enabled);
    chrome.storage.local.set({ autoAnalyzeEnabled });
    sendResponse({ ok: true, enabled: autoAnalyzeEnabled });
    return true;
  }

  if (request.action === "planAndExecute") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs[0]?.id;
      if (!tabId) {
        sendResponse({ error: "No active tab found." });
        return;
      }

      chrome.tabs.sendMessage(tabId, { action: "getDomMap" }, async (domResponse) => {
        if (chrome.runtime.lastError || !domResponse || domResponse.error) {
          sendResponse({ error: domResponse?.error || "Failed to read DOM map." });
          return;
        }

        try {
          const apiResponse = await fetch("http://localhost:8000/automation_plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              query: request.query,
              url: tabs[0].url,
              dom_map: domResponse.dom_map
            })
          });

          if (!apiResponse.ok) throw new Error("API request failed");
          const result = await apiResponse.json();
          const actions = result.actions || [];

          chrome.tabs.sendMessage(tabId, { action: "executeActionPlan", actions }, (execResponse) => {
            if (chrome.runtime.lastError || !execResponse || execResponse.error) {
              sendResponse({ error: execResponse?.error || "Failed to execute actions." });
              return;
            }

            sendResponse({
              message: `Executed ${actions.length} action(s).`,
              results: execResponse.results
            });
          });
        } catch (err) {
          sendResponse({ error: "API error: " + err.message });
        }
      });
    });
    return true;
  }
});