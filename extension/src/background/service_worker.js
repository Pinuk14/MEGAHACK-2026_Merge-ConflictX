// Handles communication between popup and content script
let autoAnalyzeEnabled = false;
let assistModeEnabled = false;
let autoFillEnabled = true;
let continuousLoopEnabled = false;
let copilotSettings = {
  userProfile: {},
  siteCredentials: {}
};
const observerBuffers = {};
const observerTickState = {};
const autoAnalyzeState = {};
const mappingBuffers = {};
const mappingFlushState = {};

chrome.storage.local.get(["autoAnalyzeEnabled", "copilotSettings"], (result) => {
  if (typeof result.autoAnalyzeEnabled === "boolean") {
    autoAnalyzeEnabled = result.autoAnalyzeEnabled;
  }
  if (result.copilotSettings && typeof result.copilotSettings === "object") {
    copilotSettings = result.copilotSettings;
    assistModeEnabled = Boolean(result.copilotSettings.assistModeEnabled);
    autoFillEnabled = typeof result.copilotSettings.autoFillEnabled === "boolean"
      ? result.copilotSettings.autoFillEnabled
      : true;
    continuousLoopEnabled = Boolean(result.copilotSettings.continuousLoopEnabled);
  }
});

function ensureObserverBucket(tabId) {
  if (!observerBuffers[tabId]) observerBuffers[tabId] = [];
  if (!observerTickState[tabId]) {
    observerTickState[tabId] = { lastTickAt: 0, inFlight: false };
  }
}

function enqueueObserverEvent(tabId, eventPayload) {
  ensureObserverBucket(tabId);
  observerBuffers[tabId].push(eventPayload);
  if (observerBuffers[tabId].length > 40) {
    observerBuffers[tabId] = observerBuffers[tabId].slice(-40);
  }

  // Also enqueue for mapping if relevant
  try {
    enqueueMappingStep(tabId, eventPayload);
  } catch (e) {
    // ignore mapping enqueue errors
  }
}

function ensureMappingBucket(tabId) {
  if (!mappingBuffers[tabId]) mappingBuffers[tabId] = [];
  if (!mappingFlushState[tabId]) mappingFlushState[tabId] = { inFlight: false, lastFlush: 0 };
}

function enqueueMappingStep(tabId, event) {
  ensureMappingBucket(tabId);
  // Only record a mapping step when the observed page URL actually changes.
  // This avoids creating many map entries for repeated DOM events on the same page.
  const buf = mappingBuffers[tabId];
  const curUrl = normalizePageUrl(event?.url || "");
  let lastUrl = null;
  if (buf && buf.length > 0) {
    const last = buf[buf.length - 1];
    lastUrl = normalizePageUrl(last?.url || "");
  }

  // If the URL hasn't changed, skip adding a new mapping step.
  if (lastUrl && lastUrl === curUrl) {
    // Optionally, we could update the timestamp of the last step instead of pushing a duplicate.
    try {
      if (buf && buf.length > 0) buf[buf.length - 1].ts = event.ts || Date.now();
    } catch (e) {
      // ignore
    }
  } else {
    // Only keep recent N steps per tab
    mappingBuffers[tabId].push(event);
    if (mappingBuffers[tabId].length > 120) mappingBuffers[tabId] = mappingBuffers[tabId].slice(-120);
  }

  // flush heuristics: flush when buffer large or on clicks/navigation
  const type = String(event?.type || "").toUpperCase();
  // Trigger a flush for navigation-style events or when buffer grows large.
  if (["NAVIGATE", "PAGE_OBSERVED"].includes(type) || mappingBuffers[tabId].length >= 20) {
    scheduleMappingFlush(tabId, 300);
  }
}

function scheduleMappingFlush(tabId, delayMs = 800) {
  ensureMappingBucket(tabId);
  const state = mappingFlushState[tabId];
  if (state.timer) clearTimeout(state.timer);
  state.timer = setTimeout(() => flushMappingBuffer(tabId), delayMs);
}

async function flushMappingBuffer(tabId) {
  ensureMappingBucket(tabId);
  const state = mappingFlushState[tabId];
  if (state.inFlight) return;
  const buf = mappingBuffers[tabId] || [];
  if (!buf.length) return;

  state.inFlight = true;
  const payload = {
    session_id: null,
    steps: buf.map((e) => ({
      url: e.url || null,
      title: e.title || null,
      selector: e.element?.selector || (e.dom_map ? null : null),
      action: e.type || null,
      value: e.value || (e.element && (e.element.value || e.element.text)) || null,
      timestamp: e.ts || Date.now()
    })),
    metadata: { source: "extension_observer" }
  };

  try {
    const res = await postWithRetries("http://127.0.0.1:8000/mapping/upload", payload, 2);
    if (res.ok) {
      // Clear buffer on success
      mappingBuffers[tabId] = [];
      state.lastFlush = Date.now();
    }
  } catch (e) {
    // ignore
  } finally {
    state.inFlight = false;
  }
}

async function ensureObserverRunning(tabId) {
  if (!continuousLoopEnabled || !assistModeEnabled) return;
  await sendMessageToTabWithInject(tabId, {
    action: "startContinuousObservation",
    config: {
      minEventIntervalMs: 220,
      emitClicks: true,
      emitFocus: true,
      emitInput: true,
      emitScroll: true,
      emitMutations: true
    }
  });
}

async function stopObserver(tabId) {
  await sendMessageToTabWithInject(tabId, { action: "stopContinuousObservation" });
}

async function runContinuousLoopTick(tabId) {
  ensureObserverBucket(tabId);
  const state = observerTickState[tabId];
  const now = Date.now();
  if (state.inFlight) return;
  if ((now - state.lastTickAt) < 1500) return;
  if ((observerBuffers[tabId] || []).length === 0) return;

  state.inFlight = true;
  state.lastTickAt = now;

  try {
    const events = observerBuffers[tabId].splice(0, 12);
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || tab.id !== tabId) {
      state.inFlight = false;
      return;
    }

    const domResponse = await sendMessageToTabWithInject(tabId, { action: "getDomMap" });
    const domMap = domResponse && !domResponse.error ? domResponse.dom_map : {};

    const payload = {
      url: tab.url,
      title: tab.title || "",
      events,
      dom_map: domMap,
      user_memory: {
        profile: copilotSettings?.userProfile || {},
        site_credentials: getSiteCredentialsForUrl(tab.url)
      }
    };

    const result = await postWithRetries("http://127.0.0.1:8000/agent_loop_tick", payload, 2);
    if (result.ok && result.json && Array.isArray(result.json.actions) && result.json.actions.length > 0) {
      await sendMessageToTabWithInject(tabId, { action: "executeActionPlan", actions: result.json.actions });
    }
  } catch (e) {
    // ignore per-tick errors; next events will trigger another tick
  } finally {
    state.inFlight = false;
  }
}

function normalizeHostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./i, "").toLowerCase();
  } catch (e) {
    return "";
  }
}

function getSiteCredentialsForUrl(url) {
  const host = normalizeHostname(url);
  if (!host) return null;
  const credentials = copilotSettings?.siteCredentials || {};
  return credentials[host] || null;
}

function shortSummaryText(summary) {
  if (!summary) return "";
  if (typeof summary === "string") return summary.slice(0, 400);
  if (summary.short_summary) return String(summary.short_summary).slice(0, 400);
  if (summary.executive_summary && typeof summary.executive_summary === "string") {
    return summary.executive_summary.slice(0, 400);
  }
  return "";
}

function normalizePageUrl(url) {
  try {
    const u = new URL(url);
    u.hash = "";
    return u.toString();
  } catch (e) {
    return String(url || "");
  }
}

function buildAutoAnalyzeKey(url, title) {
  return `${normalizePageUrl(url)}::${String(title || "").slice(0, 140)}`;
}

function maybeAutoAnalyze(tabId, tab, reason = "") {
  if (!autoAnalyzeEnabled) return;
  if (!tab?.url || !String(tab.url).startsWith("http")) return;

  const key = buildAutoAnalyzeKey(tab.url, tab.title || "");
  if (autoAnalyzeState[tabId]?.key === key) return;

  if (autoAnalyzeState[tabId]?.timer) {
    clearTimeout(autoAnalyzeState[tabId].timer);
  }

  autoAnalyzeState[tabId] = {
    key,
    reason,
    timer: setTimeout(() => {
      analyzeTab(tabId);
    }, 900)
  };
}

async function applyAutoAssistToTab(tabId, url) {
  if (!assistModeEnabled) return;
  const siteCredentials = getSiteCredentialsForUrl(url);
  await sendMessageToTabWithInject(tabId, {
    action: "applyAutoAssist",
    enabled: assistModeEnabled,
    autofillEnabled: autoFillEnabled,
    profile: copilotSettings?.userProfile || {},
    credentials: siteCredentials
  });
}

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

// Helper: fetch remote document content (arrayBuffer -> base64). Returns { ok, base64, error }
async function fetchDocumentContentAsBase64(url) {
  try {
    const resp = await fetch(url, { method: "GET", cache: "no-store" });
    if (!resp.ok) return { ok: false, error: `Fetch failed: ${resp.status} ${resp.statusText}` };
    const buf = await resp.arrayBuffer();
    const bytes = new Uint8Array(buf);
    // Convert to base64 in chunks to avoid call stack limits
    let binary = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.subarray(i, i + chunkSize);
      binary += String.fromCharCode.apply(null, chunk);
    }
    const base64 = btoa(binary);
    return { ok: true, base64 };
  } catch (err) {
    return { ok: false, error: err.message || String(err) };
  }
}

// Helper: POST with retries + exponential backoff. Stores simple telemetry in chrome.storage.local
async function postWithRetries(url, payload, attempts = 3) {
  let lastError = null;
  for (let i = 0; i < attempts; i++) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const bodyText = await res.text().catch(() => "<no body>");
        lastError = `HTTP ${res.status} ${res.statusText} — ${bodyText}`;
        // treat as retryable for 5xx; for 4xx break early
        if (res.status >= 400 && res.status < 500) break;
      } else {
        const clone = res.clone();
        let json = null;
        try {
          json = await clone.json().catch(() => null);
        } catch (e) {
          json = null;
        }
        // record success telemetry
        chrome.storage.local.get(["telemetry"], (obj) => {
          const t = obj.telemetry || { successes: 0, failures: 0 };
          t.successes = (t.successes || 0) + 1;
          chrome.storage.local.set({ telemetry: t });
        });
        // store network log (size-limited previews)
        try {
          const preview = (obj) => {
            try {
              return JSON.stringify(obj).slice(0, 10000);
            } catch (e) {
              return String(obj).slice(0, 10000);
            }
          };
          const respText = await res.text().catch(() => "<no body>");
          const entry = {
            ts: Date.now(),
            url,
            status: res.status,
            payload_preview: preview(payload),
            response_preview: respText.slice(0, 10000),
          };
          chrome.storage.local.get(["networkLogs"], (s) => {
            const logs = s.networkLogs || [];
            logs.push(entry);
            // keep last 50 entries
            const slice = logs.slice(-50);
            chrome.storage.local.set({ networkLogs: slice });
          });
        } catch (e) {
          // ignore logging errors
        }
        return { ok: true, json };
      }
    } catch (err) {
      lastError = err.message || String(err);
    }

    // record a failure attempt
    chrome.storage.local.get(["telemetry"], (obj) => {
      const t = obj.telemetry || { successes: 0, failures: 0 };
      t.failures = (t.failures || 0) + 1;
      chrome.storage.local.set({ telemetry: t });
    });

    // backoff before next try
    const delay = Math.min(2000, 500 * Math.pow(2, i));
    await new Promise(r => setTimeout(r, delay));
  }
  return { ok: false, error: lastError || "Unknown error" };
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
          // Build payload similar to interactive analyze: include combined text and attachments if available
          const main = (response.data?.text_content?.main_content || "").trim();
          const bodyFallback = (response.data?.full_text || response.data?.text || "").trim();
          const text = (main.length >= 120 ? main : bodyFallback);

          // Decide if title looks like a real filename/title or a transient page
          const title = (response.data.metadata?.title || "").trim();
          const isQuiz = /quiz/i.test(title);
          const source_filename = title && title.length > 5 && !isQuiz ? title : null;

          const payload = {
            text: text || bodyFallback || "",
            // leave document_id null so backend generates a stable `api-...` id
            document_id: null,
            source_filename: source_filename,
            persist_output: true,
            main_html: response.data?.text_content?.main_html || null,
            full_html: response.data?.full_html || response.data?.text_content?.main_html || null,
            metadata: response.data?.metadata || null,
            attachments: []
          };

          const docs = response.data?.detected_documents || [];
          for (const doc of docs) {
            if (doc.src || doc.href) {
              const url = doc.src || doc.href;
              const fetchResult = await fetchDocumentContentAsBase64(url);
              if (fetchResult.ok) payload.attachments.push({ type: doc.type || "unknown", href: url, base64: fetchResult.base64 });
              else payload.attachments.push({ type: doc.type || "unknown", href: url, error: fetchResult.error });
            }
          }

          const postResult = await postWithRetries("http://127.0.0.1:8000/analyze", payload, 2);
          if (!postResult.ok) console.warn("Auto analyze API error:", postResult.error);
          else if (assistModeEnabled && postResult.json) {
            const summary = postResult.json?.insight?.executive_summary || postResult.json?.insight?.summary || null;
            let overlayText = shortSummaryText(summary);

            const quizData = response.data?.quiz_data || {};
            if ((quizData.question_count || 0) > 0) {
              const quizPayload = {
                url: response.data?.metadata?.url || null,
                title: response.data?.metadata?.title || null,
                full_text: response.data?.full_text || text,
                full_html: response.data?.full_html || response.data?.text_content?.main_html || null,
                analysis_summary: summary,
                quiz_data: quizData
              };

              const quizPlanResult = await postWithRetries("http://127.0.0.1:8000/quiz_solve", quizPayload, 2);
              if (quizPlanResult.ok) {
                const quizPlan = quizPlanResult.json || {};
                const answers = Array.isArray(quizPlan.answers) ? quizPlan.answers : [];
                if (answers.length > 0) {
                  const answerLines = answers
                    .map((ans) => `Q${ans.question_index}: ${ans.selected_option_text || "(no option selected)"}`)
                    .join("\n");
                  overlayText = [overlayText, "Quiz answers:", answerLines].filter(Boolean).join("\n\n");
                }
              }
            }

            if (overlayText) {
              await sendMessageToTabWithInject(tabId, { action: "showSummaryOverlay", summary: overlayText });
            }
          }
        } catch (err) {
          console.warn("Auto analyze API exception:", err.message || String(err));
        }

      resolve();
    })();
  });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!tab?.url || !tab.url.startsWith("http")) return;

  if (changeInfo.status === "complete" || typeof changeInfo.url === "string") {
    if (autoAnalyzeEnabled) {
      maybeAutoAnalyze(tabId, tab, changeInfo.status === "complete" ? "load_complete" : "url_changed");
    }

    if (assistModeEnabled) {
      applyAutoAssistToTab(tabId, tab.url);
    }

    if (continuousLoopEnabled && assistModeEnabled) {
      ensureObserverRunning(tabId);
    } else {
      stopObserver(tabId);
    }
  }
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (!tab?.url || !String(tab.url).startsWith("http")) return;
    if (autoAnalyzeEnabled) maybeAutoAnalyze(activeInfo.tabId, tab, "tab_activated");
    if (assistModeEnabled) applyAutoAssistToTab(activeInfo.tabId, tab.url);
    if (continuousLoopEnabled && assistModeEnabled) ensureObserverRunning(activeInfo.tabId);
  } catch (e) {
    // ignore activation errors
  }
});
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "observerEvent") {
    const tabId = sender?.tab?.id;
    if (!tabId || !continuousLoopEnabled || !assistModeEnabled) {
      sendResponse({ ok: true, ignored: true });
      return true;
    }
    enqueueObserverEvent(tabId, request.event || {});
    runContinuousLoopTick(tabId);
    sendResponse({ ok: true, queued: true });
    return true;
  }

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
        const main = (response.data?.text_content?.main_content || "").trim();
        const bodyFallback = (response.data?.full_text || response.data?.text || "").trim();
        const text = (main.length >= 120 ? main : bodyFallback);

        if (!text || text.length < 20) {
          sendResponse({ error: "Page content too short to analyze (need >=20 characters)." });
          return;
        }

        const title = (response.data.metadata?.title || "").trim();
        const isQuiz = /quiz/i.test(title);
        const source_filename = title && title.length > 5 && !isQuiz ? title : null;

        const payload = {
          text: text,
          document_id: null,
          source_filename: source_filename,
          persist_output: true,
          main_html: response.data?.text_content?.main_html || null,
          full_html: response.data?.full_html || response.data?.text_content?.main_html || null,
          metadata: response.data?.metadata || null,
          attachments: []
        };

        // Attempt to pre-fetch detected documents (PDFs, links) and include as base64 attachments when possible
        const docs = response.data?.detected_documents || [];
        for (const doc of docs) {
          try {
            if (doc.src || doc.href) {
              const url = doc.src || doc.href;
              const fetchResult = await fetchDocumentContentAsBase64(url);
              if (fetchResult.ok) {
                payload.attachments.push({ type: doc.type || "unknown", href: url, base64: fetchResult.base64 });
              } else {
                // include link-only fallback
                payload.attachments.push({ type: doc.type || "unknown", href: url, error: fetchResult.error });
              }
            }
          } catch (err) {
            payload.attachments.push({ type: doc.type || "unknown", href: doc.href || doc.src || "", error: err.message || String(err) });
          }
        }
        try {
          const postResult = await postWithRetries("http://127.0.0.1:8000/analyze", payload, 3);
          if (!postResult.ok) {
            sendResponse({ error: "API error: " + (postResult.error || "request failed") });
            return;
          }

          const result = postResult.json || {};
          const summary = result?.insight?.executive_summary || result?.insight?.summary || result;

          // Quiz flow: ask backend for answer actions using scraped quiz structure + URL mapping
          const quizData = response.data?.quiz_data || {};
          let quizExecution = null;

          if ((quizData.question_count || 0) > 0) {
            const quizPayload = {
              url: response.data?.metadata?.url || null,
              title: response.data?.metadata?.title || null,
              full_text: response.data?.full_text || text,
              full_html: response.data?.full_html || response.data?.text_content?.main_html || null,
              analysis_summary: summary,
              quiz_data: quizData
            };

            console.log("Quiz scrape diagnostics", {
              question_count: quizData.question_count || 0,
              submit_candidates: Array.isArray(quizData.submit_candidates) ? quizData.submit_candidates.length : 0,
              first_question: quizData.questions?.[0]?.question_text || null
            });

            const quizPlanResult = await postWithRetries("http://127.0.0.1:8000/quiz_solve", quizPayload, 2);
            if (quizPlanResult.ok) {
              const quizPlan = quizPlanResult.json || {};
              const actions = Array.isArray(quizPlan.actions) ? quizPlan.actions : [];
              const answers = Array.isArray(quizPlan.answers) ? quizPlan.answers : [];

              console.log("Quiz plan diagnostics", {
                answers_count: answers.length,
                actions_count: actions.length,
                first_action: actions[0] || null
              });

              // Safety: do not execute if there are no answer selections.
              const answerActions = actions.filter((a) => a?.type === "CLICK" && a?.target);

              if (answers.length === 0 || answerActions.length === 0) {
                quizExecution = {
                  answers,
                  actions,
                  execution: {
                    ok: false,
                    message: "Quiz execution skipped: no answer actions generated.",
                  }
                };
              } else {
                const execResponse = await sendMessageToTabWithInject(tabId, { action: "executeActionPlan", actions });
                quizExecution = {
                  answers,
                  actions,
                  execution: execResponse
                };
              }
            } else {
              quizExecution = {
                answers: [],
                actions: [],
                execution: { ok: false, message: "Quiz planning failed", error: quizPlanResult.error }
              };
            }
          }

          sendResponse({
            summary,
            quiz_execution: quizExecution,
            diagnostics: {
              scraped_question_count: response.data?.quiz_data?.question_count || 0,
              scraped_submit_candidates: Array.isArray(response.data?.quiz_data?.submit_candidates)
                ? response.data.quiz_data.submit_candidates.length
                : 0,
              scraped_full_text_length: (response.data?.full_text || "").length
            }
          });
        } catch (err) {
          sendResponse({ error: "API error: " + (err.message || String(err)) });
        }
      })();
    });
    return true;
  }

  if (request.action === "setAutoAnalyze") {
    autoAnalyzeEnabled = Boolean(request.enabled);
    chrome.storage.local.set({ autoAnalyzeEnabled });
    if (autoAnalyzeEnabled) {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const tab = tabs?.[0];
        const tabId = tab?.id;
        if (!tabId || !tab?.url || !tab.url.startsWith("http")) return;
        maybeAutoAnalyze(tabId, tab, "toggle_enabled");
      });
    }
    sendResponse({ ok: true, enabled: autoAnalyzeEnabled });
    return true;
  }

  if (request.action === "setCopilotSettings") {
    const incoming = request.settings && typeof request.settings === "object" ? request.settings : {};
    copilotSettings = {
      ...copilotSettings,
      ...incoming,
      userProfile: incoming.userProfile || copilotSettings.userProfile || {},
      siteCredentials: incoming.siteCredentials || copilotSettings.siteCredentials || {}
    };
    assistModeEnabled = Boolean(copilotSettings.assistModeEnabled);
    autoFillEnabled = typeof copilotSettings.autoFillEnabled === "boolean" ? copilotSettings.autoFillEnabled : true;
    continuousLoopEnabled = Boolean(copilotSettings.continuousLoopEnabled);
    chrome.storage.local.set({ copilotSettings });
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs?.[0]?.id;
      const url = tabs?.[0]?.url;
      if (!tabId || !url || !url.startsWith("http")) return;
      if (continuousLoopEnabled && assistModeEnabled) ensureObserverRunning(tabId);
      else stopObserver(tabId);
    });
    sendResponse({ ok: true, settings: copilotSettings });
    return true;
  }

  if (request.action === "getCopilotSettings") {
    sendResponse({ ok: true, settings: copilotSettings });
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
          const planPayload = { query: request.query, url: tabs[0].url, dom_map: domResponse.dom_map, full_html: null };
          // try to fetch full HTML from the page if available via content script
          try {
            const pageResp = await sendMessageToTabWithInject(tabId, { action: "extractPageContent" });
            if (pageResp && pageResp.data && pageResp.data.full_html) planPayload.full_html = pageResp.data.full_html;
          } catch (e) {
            // ignore; plan will still use dom_map
          }
          const postResult = await postWithRetries("http://127.0.0.1:8000/automation_plan", planPayload, 3);
          if (!postResult.ok) {
            sendResponse({ error: "API error: " + (postResult.error || "request failed") });
            return;
          }
          const result = postResult.json || {};
          const actions = result.actions || [];

          const execResponse = await sendMessageToTabWithInject(tabId, { action: "executeActionPlan", actions });
          if (!execResponse || execResponse.error) {
            sendResponse({ error: execResponse?.error || "Failed to execute actions." });
            return;
          }

          const results = execResponse.results || [];
          const failedCount = results.filter((r) => r.status !== "ok").length;
          const summaryMessage = execResponse.message || (failedCount === 0
            ? `Executed ${actions.length} action(s) successfully.`
            : `Executed ${actions.length} action(s) with ${failedCount} failure(s).`);

          sendResponse({ message: summaryMessage, results });
        } catch (err) {
          sendResponse({ error: "API error: " + (err.message || String(err)) });
        }
      })();
    });
    return true;
  }

  if (request.action === "executeMappedPlan") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs?.[0]?.id;
      if (!tabId) {
        sendResponse({ error: "No active tab found." });
        return;
      }

      (async () => {
        try {
          const execResponse = await sendMessageToTabWithInject(tabId, { action: "executeActionPlan", actions: request.actions || [] });
          if (!execResponse || execResponse.error) {
            sendResponse({ error: execResponse?.error || "Failed to execute actions." });
            return;
          }

          sendResponse({ ok: true, message: execResponse.message || "Executed mapped plan.", results: execResponse.results || [] });
        } catch (err) {
          sendResponse({ error: err.message || String(err) });
        }
      })();
    });
    return true;
  }

  if (request.action === "validateMappedPlan") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs?.[0]?.id;
      if (!tabId) {
        sendResponse({ error: "No active tab found." });
        return;
      }

      (async () => {
        try {
          const resp = await sendMessageToTabWithInject(tabId, { action: "validateActionPlan", actions: request.actions || [] });
          if (!resp || resp.error) {
            sendResponse({ ok: false, error: resp?.error || "Validation error" });
            return;
          }
          sendResponse({ ok: true, validations: resp.validations || [] });
        } catch (err) {
          sendResponse({ ok: false, error: err?.message || String(err) });
        }
      })();
    });
    return true;
  }
});