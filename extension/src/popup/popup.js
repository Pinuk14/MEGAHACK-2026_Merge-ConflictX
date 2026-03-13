const chat = document.getElementById("chat");
const promptInput = document.getElementById("prompt");
const sendBtn = document.getElementById("sendBtn");
const mapGoalInput = document.getElementById("mapGoal");
const planMapBtn = document.getElementById("planMapBtn");
const chatStatusEl = document.getElementById("chatStatus");
const chatErrorEl = document.getElementById("chatError");

const analyzeBtn = document.getElementById("analyzeBtn");
const autoAnalyzeToggle = document.getElementById("autoAnalyzeToggle");
const analysisStatusEl = document.getElementById("analysisStatus");
const analysisSummaryEl = document.getElementById("analysisSummary");
const analysisErrorEl = document.getElementById("analysisError");
const assistModeToggle = document.getElementById("assistModeToggle");
const autofillToggle = document.getElementById("autofillToggle");
const continuousLoopToggle = document.getElementById("continuousLoopToggle");
const profileName = document.getElementById("profileName");
const profileEmail = document.getElementById("profileEmail");
const profilePhone = document.getElementById("profilePhone");
const profileAddress = document.getElementById("profileAddress");
const saveProfileBtn = document.getElementById("saveProfileBtn");
const domainLabel = document.getElementById("domainLabel");
const siteUsername = document.getElementById("siteUsername");
const siteEmail = document.getElementById("siteEmail");
const sitePassword = document.getElementById("sitePassword");
const saveSiteCredsBtn = document.getElementById("saveSiteCredsBtn");
const copilotStatus = document.getElementById("copilotStatus");

let activeDomain = "";
let cachedSettings = {
  assistModeEnabled: false,
  autoFillEnabled: true,
  continuousLoopEnabled: false,
  userProfile: {},
  siteCredentials: {}
};

function appendMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  msg.innerText = `${role === "user" ? "You" : "Agent"}: ${text}`;
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
}

function setChatStatus(text) {
  chatStatusEl.innerText = text;
}

function setChatError(text) {
  chatErrorEl.innerText = text;
}

function setAnalysisStatus(text) {
  analysisStatusEl.innerText = text;
}

function setAnalysisError(text) {
  analysisErrorEl.innerText = text;
}

function setAnalysisSummary(text) {
  analysisSummaryEl.innerText = text;
}

function setCopilotStatus(text) {
  copilotStatus.innerText = text;
}

function normalizeHostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./i, "").toLowerCase();
  } catch (e) {
    return "";
  }
}

function collectSettingsFromUI() {
  return {
    assistModeEnabled: Boolean(assistModeToggle.checked),
    autoFillEnabled: Boolean(autofillToggle.checked),
    continuousLoopEnabled: Boolean(continuousLoopToggle.checked),
    userProfile: {
      name: profileName.value.trim(),
      email: profileEmail.value.trim(),
      phone: profilePhone.value.trim(),
      address: profileAddress.value.trim()
    },
    siteCredentials: {
      ...(cachedSettings.siteCredentials || {}),
      ...(activeDomain
        ? {
            [activeDomain]: {
              username: siteUsername.value.trim(),
              email: siteEmail.value.trim(),
              password: sitePassword.value
            }
          }
        : {})
    }
  };
}

function applySettingsToUI(settings) {
  cachedSettings = {
    assistModeEnabled: Boolean(settings?.assistModeEnabled),
    autoFillEnabled: typeof settings?.autoFillEnabled === "boolean" ? settings.autoFillEnabled : true,
    continuousLoopEnabled: Boolean(settings?.continuousLoopEnabled),
    userProfile: settings?.userProfile || {},
    siteCredentials: settings?.siteCredentials || {}
  };

  assistModeToggle.checked = cachedSettings.assistModeEnabled;
  autofillToggle.checked = cachedSettings.autoFillEnabled;
  continuousLoopToggle.checked = cachedSettings.continuousLoopEnabled;
  profileName.value = cachedSettings.userProfile.name || "";
  profileEmail.value = cachedSettings.userProfile.email || "";
  profilePhone.value = cachedSettings.userProfile.phone || "";
  profileAddress.value = cachedSettings.userProfile.address || "";

  const site = (cachedSettings.siteCredentials || {})[activeDomain] || {};
  siteUsername.value = site.username || "";
  siteEmail.value = site.email || "";
  sitePassword.value = site.password || "";
}

function persistSettings(settings, statusText) {
  cachedSettings = settings;
  chrome.storage.local.set({ copilotSettings: settings }, () => {
    chrome.runtime.sendMessage({ action: "setCopilotSettings", settings }, () => {
      setCopilotStatus(statusText);
    });
  });
}

function bootstrapCopilotSettings() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const url = tabs?.[0]?.url || "";
    activeDomain = normalizeHostname(url);
    domainLabel.innerText = `Current site: ${activeDomain || "unknown"}`;

    chrome.storage.local.get(["copilotSettings"], (result) => {
      applySettingsToUI(result.copilotSettings || cachedSettings);
    });
  });
}

function formatSummary(summary) {
  if (!summary) return "";
  if (typeof summary === "string") return summary;

  const short = summary.short_summary ? `Summary: ${summary.short_summary}` : "";
  const keyPoints = Array.isArray(summary.key_points) && summary.key_points.length
    ? `Key points:\n- ${summary.key_points.join("\n- ")}`
    : "";
  const actions = Array.isArray(summary.recommended_actions) && summary.recommended_actions.length
    ? `Recommended actions:\n- ${summary.recommended_actions.join("\n- ")}`
    : "";

  return [short, keyPoints, actions].filter(Boolean).join("\n\n");
}

function runAnalyze() {
  setAnalysisError("");
  setAnalysisSummary("");
  setAnalysisStatus("Analyzing...");
  console.log("Sending scrapeAndAnalyze message");
  chrome.runtime.sendMessage({ action: "scrapeAndAnalyze" }, (response) => {
    console.log("Received response from scrapeAndAnalyze", response);
    setAnalysisStatus("");
    if (response?.summary) {
      let summaryText = formatSummary(response.summary);

      const quizExecution = response?.quiz_execution;
      const diagnostics = response?.diagnostics;
      if (quizExecution) {
        const executionOk = Boolean(quizExecution?.execution?.ok);
        const answers = Array.isArray(quizExecution?.answers) ? quizExecution.answers : [];
        const answerLines = answers
          .map((ans) => `Q${ans.question_index}: ${ans.selected_option_text || "(no option selected)"}`)
          .join("\n");

        if (executionOk) {
          appendMessage("bot", "Quiz automation executed successfully.");
        } else {
          appendMessage("bot", `Quiz automation status: ${quizExecution?.execution?.message || "not executed"}`);
        }

        if (answerLines) {
          appendMessage("bot", `Selected answers:\n${answerLines}`);
          summaryText = [summaryText, "Quiz answers:", answerLines].filter(Boolean).join("\n\n");
        }
      }

      setAnalysisSummary(summaryText);

      if (diagnostics) {
        appendMessage(
          "bot",
          `Diagnostics: questions=${diagnostics.scraped_question_count}, submitButtons=${diagnostics.scraped_submit_candidates}, textLen=${diagnostics.scraped_full_text_length}`
        );
      }
    } else if (response?.error) {
      setAnalysisError(response.error);
    } else {
      setAnalysisError("Unknown error occurred.");
    }
  });
}

async function sendAutomationRequest() {
  const query = promptInput.value.trim();
  if (!query) return;

  setChatError("");
  appendMessage("user", query);
  promptInput.value = "";
  setChatStatus("Planning actions...");

  chrome.runtime.sendMessage({ action: "planAndExecute", query }, (response) => {
    setChatStatus("");
    if (response?.message) {
      appendMessage("bot", response.message);
      if (Array.isArray(response.results)) {
        const failed = response.results.filter((result) => result.status !== "ok");
        const details = response.results
          .map((result) => {
            const actionType = result.action?.type || "ACTION";
            if (result.status === "ok") return `${actionType}: ok`;
            return `${actionType}: failed (${result.message || "unknown error"})`;
          })
          .join("; ");

        if (details) appendMessage("bot", details);
        appendMessage(
          "bot",
          failed.length === 0
            ? "Automation executed successfully."
            : `Automation completed with ${failed.length} failed action(s).`
        );
      }
    } else if (response?.error) {
      setChatError(response.error);
    } else {
      setChatError("Unknown error occurred.");
    }
  });
}

async function planMapGoalRequest() {
  const goal = (mapGoalInput && mapGoalInput.value || "").trim();
  if (!goal) return setChatError("Provide a goal to plan.");

  setChatError("");
  appendMessage("user", `Plan goal: ${goal}`);
  setChatStatus("Requesting map planner...");

  try {
    const listResp = await fetch("http://127.0.0.1:8000/mapping/list");
    const listJson = await listResp.json();
    const maps = Array.isArray(listJson.maps) ? listJson.maps : [];
    if (!maps.length) {
      setChatError("No maps available. Let the extension observe navigation first.");
      setChatStatus("");
      return;
    }
    const mapId = maps[0].map_id;

    const postResp = await fetch(`http://127.0.0.1:8000/mapping/${mapId}/plan_goal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal })
    });
    const planJson = await postResp.json();
    setChatStatus("");

    if (!planJson.ok) {
      setChatError(planJson.message || planJson.error || "Planner failed");
      return;
    }

    const actions = planJson.actions || [];
    if (!actions.length) {
      appendMessage("bot", "Planner returned no actions.");
      return;
    }

    const lines = actions.map((a, i) => `${i + 1}. ${a.type} -> ${a.target || a.url || a.value || "(no target)"}`).join("\n");
    appendMessage("bot", `Planned actions:\n${lines}`);

    // Validate actions live on the active tab before executing
    chrome.runtime.sendMessage({ action: "validateMappedPlan", actions }, (valResp) => {
      if (!valResp || !valResp.ok) {
        appendMessage("bot", `Validation failed: ${valResp?.error || 'unknown error'}`);
        return;
      }

      const validations = Array.isArray(valResp.validations) ? valResp.validations : [];
      const validCount = validations.filter(v => v.ok).length;
      const invalidCount = validations.length - validCount;
      const details = validations.map((v, i) => `${i + 1}. ${v.ok ? 'OK' : 'BAD'} - ${v.action.type || v.action?.type || 'ACTION'} ${v.action.target || v.action.url || ''} ${v.reason ? `(${v.reason})` : ''}`).join("\n");

      appendMessage("bot", `Validation: ${validCount}/${validations.length} valid.\n${details}`);

      const proceed = invalidCount === 0 ? true : confirm(`Validation found ${invalidCount} potential problems. Proceed to execute anyway?`);
      if (!proceed) {
        appendMessage("bot", "Execution cancelled by user.");
        return;
      }

      chrome.runtime.sendMessage({ action: "executeMappedPlan", actions }, (execResp) => {
        if (execResp?.error) {
          appendMessage("bot", `Execution error: ${execResp.error}`);
        } else if (execResp?.ok) {
          appendMessage("bot", execResp.message || "Executed mapped plan.");
        } else {
          appendMessage("bot", "Execution completed (unknown status)");
        }
      });
    });
  } catch (err) {
    setChatStatus("");
    setChatError(err.message || String(err));
  }
}

analyzeBtn.addEventListener("click", runAnalyze);
sendBtn.addEventListener("click", sendAutomationRequest);
if (planMapBtn) planMapBtn.addEventListener("click", planMapGoalRequest);
promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendAutomationRequest();
});

autoAnalyzeToggle.addEventListener("change", (event) => {
  const enabled = event.target.checked;
  chrome.runtime.sendMessage({ action: "setAutoAnalyze", enabled }, (response) => {
    if (response?.error) {
      setAnalysisError(response.error);
      autoAnalyzeToggle.checked = !enabled;
      return;
    }
    setAnalysisStatus(enabled ? "Auto-analyze enabled." : "Auto-analyze disabled.");
  });
});

assistModeToggle.addEventListener("change", () => {
  const settings = collectSettingsFromUI();
  persistSettings(settings, settings.assistModeEnabled ? "Assist mode enabled." : "Assist mode disabled.");
});

autofillToggle.addEventListener("change", () => {
  const settings = collectSettingsFromUI();
  persistSettings(settings, settings.autoFillEnabled ? "Auto-fill enabled." : "Auto-fill disabled.");
});

continuousLoopToggle.addEventListener("change", () => {
  const settings = collectSettingsFromUI();
  persistSettings(
    settings,
    settings.continuousLoopEnabled
      ? "Continuous loop enabled."
      : "Continuous loop disabled."
  );
});

saveProfileBtn.addEventListener("click", () => {
  const settings = collectSettingsFromUI();
  persistSettings(settings, "Profile saved.");
});

saveSiteCredsBtn.addEventListener("click", () => {
  if (!activeDomain) {
    setCopilotStatus("Cannot save credentials: no active website domain.");
    return;
  }
  const settings = collectSettingsFromUI();
  persistSettings(settings, `Saved credentials for ${activeDomain}.`);
});

// Debug log to verify chrome.storage.local availability
console.log("Checking chrome.storage.local availability...");
if (chrome.storage && chrome.storage.local) {
  console.log("chrome.storage.local is available.");
  chrome.storage.local.get(["autoAnalyzeEnabled"], (result) => {
    console.log("chrome.storage.local.get result:", result);
    if (typeof result.autoAnalyzeEnabled === "boolean") {
      autoAnalyzeToggle.checked = result.autoAnalyzeEnabled;
    }
    bootstrapCopilotSettings();
  });
} else {
  console.error("chrome.storage.local is not available.");
}