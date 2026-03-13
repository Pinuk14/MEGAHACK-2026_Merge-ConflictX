// Handles communication between popup and content script
let autoAnalyzeEnabled = false;

chrome.storage.local.get(["autoAnalyzeEnabled"], (result) => {
  if (typeof result.autoAnalyzeEnabled === "boolean") {
    autoAnalyzeEnabled = result.autoAnalyzeEnabled;
  }
});

// Helper: send a message to a tab, attempt to inject the content script if no listener
function sendMessageToTabWithInject(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, async (response) => {
      if (!chrome.runtime.lastError && response) {
        resolve(response);
        return;
      }

      // If there's a runtime.lastError, try injecting the content script then retry
      try {
        await chrome.scripting.executeScript({
          target: { tabId },
          files: ["src/content_scripts/scraper.js"]
        });
      } catch (injectErr) {
        resolve({ error: "Injection error: " + (injectErr?.message || injectErr) });
        return;
      }

      // Small delay to allow script to initialize
      setTimeout(() => {
        chrome.tabs.sendMessage(tabId, message, (resp2) => {
          if (chrome.runtime.lastError || !resp2) {
            resolve({ error: resp2?.error || chrome.runtime.lastError?.message || "No response after injection" });
          } else {
            resolve(resp2);
          }
        });
      }, 200);
    });
  });
}

async function analyzeTab(tabId) {
  return new Promise((resolve) => {
    (async () => {
      const response = await sendMessageToTabWithInject(tabId, { action: "extractPageContent" });
      if (!response || response.error) {
        console.warn("Auto analyze failed:", response?.error);
        resolve();
        return;
      }

      try {
        const hash = btoa(unescape(encodeURIComponent(response.data.metadata.url + response.data.metadata.title)));
        await fetch("http://127.0.0.1:8000/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...response.data, page_hash: hash })
        });
      } catch (err) {
        console.warn("Auto analyze API error:", err.message);
      }

      resolve();
    })();
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
      (async () => {
        const response = await sendMessageToTabWithInject(tabId, { action: "extractPageContent" });
        if (!response || response.error) {
          sendResponse({ error: response?.error || "Failed to scrape page." });
          return;
        }

        // Caching: generate hash
        const hash = btoa(unescape(encodeURIComponent(response.data.metadata.url + response.data.metadata.title)));
        // Prepare payload for backend: build a robust text field
        const main = response.data?.text_content?.main_content || "";
        const headings = Array.isArray(response.data?.text_content?.headings) ? response.data.text_content.headings.join("\n\n") : "";
        const paragraphs = Array.isArray(response.data?.text_content?.paragraphs) ? response.data.text_content.paragraphs.join("\n\n") : "";
        const bodyFallback = response.data?.text || "";
        const combined = [main, headings, paragraphs, bodyFallback].filter(Boolean).join("\n\n");
        const text = combined.trim();

        if (!text || text.length < 20) {
          sendResponse({ error: "Page content too short to analyze (need >=20 characters)." });
          return;
        }

        const payload = {
          text: text,
          document_id: hash,
          source_filename: response.data.metadata?.title || "",
          persist_output: false
        };
        try {
          const apiResponse = await fetch("http://127.0.0.1:8000/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
          if (!apiResponse.ok) {
            const bodyText = await apiResponse.text().catch(() => "<no body>");
            sendResponse({ error: `API error: ${apiResponse.status} ${apiResponse.statusText} — ${bodyText}` });
            return;
          }
          const result = await apiResponse.json();
          sendResponse({ summary: result.insight?.executive_summary || result.insight?.summary || result });
        } catch (err) {
          sendResponse({ error: "API error: " + err.message });
        }
      })();
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
      (async () => {
        const domResponse = await sendMessageToTabWithInject(tabId, { action: "getDomMap" });
        if (!domResponse || domResponse.error) {
          sendResponse({ error: domResponse?.error || "Failed to read DOM map." });
          return;
        }

        try {
          const apiResponse = await fetch("http://127.0.0.1:8000/automation_plan", {
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

          const execResponse = await sendMessageToTabWithInject(tabId, { action: "executeActionPlan", actions });
          if (!execResponse || execResponse.error) {
            sendResponse({ error: execResponse?.error || "Failed to execute actions." });
            return;
          }

          sendResponse({
            message: `Executed ${actions.length} action(s).`,
            results: execResponse.results
          });
        } catch (err) {
          sendResponse({ error: "API error: " + err.message });
        }
      })();
    });
    return true;
  }
});