const chat = document.getElementById("chat");
const promptInput = document.getElementById("prompt");
const sendBtn = document.getElementById("sendBtn");
const chatStatusEl = document.getElementById("chatStatus");
const chatErrorEl = document.getElementById("chatError");

const analyzeBtn = document.getElementById("analyzeBtn");
const autoAnalyzeToggle = document.getElementById("autoAnalyzeToggle");
const analysisStatusEl = document.getElementById("analysisStatus");
const analysisSummaryEl = document.getElementById("analysisSummary");
const analysisErrorEl = document.getElementById("analysisError");

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

function runAnalyze() {
  setAnalysisError("");
  setAnalysisSummary("");
  setAnalysisStatus("Analyzing...");
  console.log("Sending scrapeAndAnalyze message");
  chrome.runtime.sendMessage({ action: "scrapeAndAnalyze" }, (response) => {
    console.log("Received response from scrapeAndAnalyze", response);
    setAnalysisStatus("");
    if (response?.summary) {
      setAnalysisSummary(response.summary);
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
        const details = response.results
          .map(result => `${result.action?.type || "ACTION"} -> ${result.status}`)
          .join("; ");
        if (details) appendMessage("bot", details);
      }
    } else if (response?.error) {
      setChatError(response.error);
    } else {
      setChatError("Unknown error occurred.");
    }
  });
}

analyzeBtn.addEventListener("click", runAnalyze);
sendBtn.addEventListener("click", sendAutomationRequest);
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

// Debug log to verify chrome.storage.local availability
console.log("Checking chrome.storage.local availability...");
if (chrome.storage && chrome.storage.local) {
  console.log("chrome.storage.local is available.");
  chrome.storage.local.get(["autoAnalyzeEnabled"], (result) => {
    console.log("chrome.storage.local.get result:", result);
    if (typeof result.autoAnalyzeEnabled === "boolean") {
      autoAnalyzeToggle.checked = result.autoAnalyzeEnabled;
    }
  });
} else {
  console.error("chrome.storage.local is not available.");
}