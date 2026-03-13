console.log("Content script initialized");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isVisible(elem) {
  if (!elem) return false;
  const style = window.getComputedStyle(elem);
  return style.display !== "none" && style.visibility !== "hidden" && elem.offsetParent !== null;
}

function norm(text) {
  return String(text || "").trim().toLowerCase();
}

const autoAssistState = {
  enabled: false,
  autofillEnabled: true,
  profile: {},
  credentials: null
};

const observerState = {
  enabled: false,
  config: {
    emitScroll: true,
    emitInput: true,
    emitClicks: true,
    emitFocus: true,
    emitMutations: true,
    minEventIntervalMs: 250
  },
  lastEventAt: 0,
  mutationObserver: null
};

let suppressObserverUntil = 0;

function buildQuickSelector(el) {
  if (!el) return "";
  if (el.id) return `#${el.id}`;
  const name = el.getAttribute?.("name");
  if (name) return `${(el.tagName || "").toLowerCase()}[name="${name}"]`;
  return (el.tagName || "").toLowerCase();
}

function inferPageType() {
  const hasPassword = document.querySelector("input[type='password']");
  const hasForm = document.querySelector("form input, form textarea, form select");
  const articleLike = document.querySelector("article, main p, h1, h2");
  if (hasPassword) return "login";
  if (hasForm) return "form";
  if (articleLike) return "article";
  return "generic";
}

function getPageSignals() {
  return {
    page_type: inferPageType(),
    forms: document.querySelectorAll("form").length,
    inputs: document.querySelectorAll("input, textarea, select").length,
    buttons: document.querySelectorAll("button, input[type='submit'], a[role='button']").length,
    links: document.querySelectorAll("a[href]").length,
    text_length: (document.body?.innerText || "").length
  };
}

function elementDescriptor(el) {
  if (!el) return {};
  return {
    tag: (el.tagName || "").toLowerCase(),
    id: el.id || "",
    name: el.name || "",
    type: el.type || "",
    text: (el.innerText || el.value || "").trim().slice(0, 120),
    placeholder: el.placeholder || "",
    aria_label: el.getAttribute?.("aria-label") || "",
    selector: buildQuickSelector(el)
  };
}

function emitObserverEvent(eventType, payload = {}) {
  if (!observerState.enabled) return;
  if (Date.now() < suppressObserverUntil) return;

  const now = Date.now();
  if (now - observerState.lastEventAt < (observerState.config.minEventIntervalMs || 250)) {
    return;
  }
  observerState.lastEventAt = now;

  chrome.runtime.sendMessage({
    action: "observerEvent",
    event: {
      ts: now,
      type: eventType,
      url: window.location.href,
      title: document.title,
      page_signals: getPageSignals(),
      ...payload
    }
  });
}

function startContinuousObservation(config = {}) {
  observerState.enabled = true;
  observerState.config = {
    ...observerState.config,
    ...(config && typeof config === "object" ? config : {})
  };

  if (observerState.config.emitMutations && !observerState.mutationObserver && document.body) {
    observerState.mutationObserver = new MutationObserver((mutations) => {
      let added = 0;
      for (const mutation of mutations) {
        added += mutation.addedNodes?.length || 0;
      }
      if (added > 0) emitObserverEvent("DOM_MUTATION", { added_nodes: added });
    });
    observerState.mutationObserver.observe(document.body, { childList: true, subtree: true });
  }

  emitObserverEvent("PAGE_OBSERVED", {});
}

function stopContinuousObservation() {
  observerState.enabled = false;
  if (observerState.mutationObserver) {
    observerState.mutationObserver.disconnect();
    observerState.mutationObserver = null;
  }
}

function getAssociatedLabelText(input) {
  if (!input) return "";
  const byFor = input.id ? document.querySelector(`label[for="${input.id}"]`) : null;
  const parentLabel = input.closest("label");
  return (byFor?.innerText || parentLabel?.innerText || "").trim();
}

function inferFieldKey(input) {
  const hay = [
    input?.name,
    input?.id,
    input?.placeholder,
    input?.autocomplete,
    input?.type,
    getAssociatedLabelText(input),
    input?.getAttribute("aria-label")
  ].join(" ").toLowerCase();

  if (/password|passcode/.test(hay)) return "password";
  if (/email|e-mail/.test(hay)) return "email";
  if (/phone|mobile|tel/.test(hay)) return "phone";
  if (/address|street|city|state|zip|postal/.test(hay)) return "address";
  if (/first\s*name|firstname/.test(hay)) return "first_name";
  if (/last\s*name|lastname|surname/.test(hay)) return "last_name";
  if (/full\s*name|your\s*name|name/.test(hay)) return "name";
  if (/user|login/.test(hay)) return "username";
  return null;
}

function valueForField(fieldKey) {
  const profile = autoAssistState.profile || {};
  const creds = autoAssistState.credentials || {};

  if (fieldKey === "password") return creds.password || "";
  if (fieldKey === "username") return creds.username || creds.email || profile.email || profile.name || "";
  if (fieldKey === "email") return creds.email || profile.email || "";
  if (fieldKey === "phone") return profile.phone || "";
  if (fieldKey === "address") return profile.address || "";
  if (fieldKey === "first_name") return profile.first_name || profile.name || "";
  if (fieldKey === "last_name") return profile.last_name || "";
  if (fieldKey === "name") return profile.name || "";
  return "";
}

function applyAutofillToInput(input) {
  if (!input || !autoAssistState.enabled || !autoAssistState.autofillEnabled) return false;
  if (!isVisible(input)) return false;
  if (input.disabled || input.readOnly) return false;
  if ((input.value || "").trim().length > 0) return false;

  const fieldKey = inferFieldKey(input);
  if (!fieldKey) return false;

  const value = valueForField(fieldKey);
  if (!value) return false;

  input.focus();
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function applyAutofillToPage() {
  const candidates = Array.from(document.querySelectorAll("input, textarea"));
  let filled = 0;
  for (const input of candidates) {
    if (applyAutofillToInput(input)) filled += 1;
  }
  return filled;
}

function showSummaryOverlay(summary) {
  if (!summary) return;
  const existing = document.getElementById("mcx-summary-overlay");
  if (existing) existing.remove();

  const card = document.createElement("div");
  card.id = "mcx-summary-overlay";
  card.style.position = "fixed";
  card.style.top = "14px";
  card.style.right = "14px";
  card.style.zIndex = "2147483647";
  card.style.maxWidth = "360px";
  card.style.background = "#111827";
  card.style.color = "#f9fafb";
  card.style.padding = "12px";
  card.style.borderRadius = "10px";
  card.style.boxShadow = "0 10px 25px rgba(0,0,0,0.25)";
  card.style.fontSize = "13px";
  card.style.lineHeight = "1.4";

  const title = document.createElement("div");
  title.style.fontWeight = "700";
  title.style.marginBottom = "8px";
  title.textContent = "Copilot Summary";

  const body = document.createElement("div");
  body.textContent = String(summary).slice(0, 500);

  const closeBtn = document.createElement("button");
  closeBtn.textContent = "Close";
  closeBtn.style.marginTop = "10px";
  closeBtn.style.border = "0";
  closeBtn.style.padding = "6px 10px";
  closeBtn.style.borderRadius = "7px";
  closeBtn.style.cursor = "pointer";
  closeBtn.onclick = () => card.remove();

  card.appendChild(title);
  card.appendChild(body);
  card.appendChild(closeBtn);
  document.body.appendChild(card);
}

document.addEventListener("focusin", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) return;
  applyAutofillToInput(target);
}, true);

document.addEventListener("click", (event) => {
  if (!observerState.enabled || !observerState.config.emitClicks) return;
  emitObserverEvent("CLICK", { element: elementDescriptor(event.target) });
}, true);

document.addEventListener("focusin", (event) => {
  if (!observerState.enabled || !observerState.config.emitFocus) return;
  emitObserverEvent("FOCUS", { element: elementDescriptor(event.target) });
}, true);

document.addEventListener("input", (event) => {
  if (!observerState.enabled || !observerState.config.emitInput) return;
  const el = event.target;
  emitObserverEvent("INPUT", {
    element: elementDescriptor(el),
    value_length: typeof el?.value === "string" ? el.value.length : 0
  });
}, true);

window.addEventListener("scroll", () => {
  if (!observerState.enabled || !observerState.config.emitScroll) return;
  emitObserverEvent("SCROLL", { y: window.scrollY, x: window.scrollX });
}, { passive: true });

function generateDOMTreeMap(node = document.body) {
  const map = { tag: node.tagName, children: [] };
  for (const child of node.children) {
    map.children.push(generateDOMTreeMap(child));
  }
  return map;
}

function generateDOMMap() {
  const inputs = Array.from(document.querySelectorAll("input, textarea"))
    .filter(isVisible)
    .map((input) => ({
      id: input.id || "",
      name: input.name || "",
      type: input.type || input.tagName.toLowerCase(),
      placeholder: input.placeholder || "",
      label: document.querySelector(`label[for="${input.id}"]`)?.innerText || ""
    }));

  const buttons = Array.from(document.querySelectorAll("button, input[type='button'], input[type='submit']"))
    .filter(isVisible)
    .map((btn) => ({
      id: btn.id || "",
      text: (btn.innerText || btn.value || "").trim(),
      class: btn.className || ""
    }));

  const forms = Array.from(document.querySelectorAll("form"))
    .filter(isVisible)
    .map((form) => ({
      id: form.id || "",
      action: form.action || ""
    }));

  const links = Array.from(document.querySelectorAll("a"))
    .filter(isVisible)
    .map((link) => ({
      href: link.href || "",
      text: (link.innerText || "").trim()
    }));

  return { inputs, buttons, forms, links };
}

function waitForDomReady() {
  return new Promise((resolve) => {
    if (document.readyState === "complete") {
      resolve();
      return;
    }
    window.addEventListener("load", () => resolve(), { once: true });
  });
}

function firstVisible(selector) {
  return Array.from(document.querySelectorAll(selector)).find(isVisible) || null;
}

function looksLikeSelector(target) {
  if (!target) return false;
  const value = String(target).trim();
  return /[.#\[\]>:+~\s]/.test(value);
}

function findByFlexibleTarget(target, selectors, options = {}) {
  if (!target) return null;
  const allowHidden = Boolean(options.allowHidden);

  const trimmed = String(target).trim();

  if (looksLikeSelector(trimmed)) {
    try {
      const direct = document.querySelector(trimmed);
      if (direct && (allowHidden || isVisible(direct))) return direct;
    } catch (err) {
      console.warn("Invalid selector target:", trimmed, err);
    }
  }

  const byId = document.getElementById(trimmed);
  if (byId && (allowHidden || isVisible(byId))) return byId;

  for (const selector of selectors) {
    const found = Array.from(document.querySelectorAll(selector)).find((el) => {
      if (!allowHidden && !isVisible(el)) return false;
      const text = norm(el.innerText || el.value || "");
      const id = norm(el.id);
      const name = norm(el.name);
      const placeholder = norm(el.placeholder);
      const ariaLabel = norm(el.getAttribute("aria-label"));
      const testId = norm(el.getAttribute("data-testid"));
      const tgt = norm(trimmed);

      if (!tgt) return false;
      return (
        id === tgt ||
        name === tgt ||
        placeholder === tgt ||
        ariaLabel === tgt ||
        testId === tgt ||
        text === tgt ||
        text.includes(tgt)
      );
    });
    if (found) return found;
  }

  return null;
}

function findInputElement(target) {
  return findByFlexibleTarget(target, ["input", "textarea"]);
}

function findClickableElement(target) {
  return findByFlexibleTarget(target, [
    "button",
    "a",
    "input[type='button']",
    "input[type='submit']",
    "input[type='radio']",
    "input[type='checkbox']",
    "label",
    "[role='button']",
    "[role='radio']"
  ], { allowHidden: true });
}

function findSelectElement(target) {
  return findByFlexibleTarget(target, ["select"]);
}

function findDownloadLink(target) {
  const fileExtPattern = /\.(pdf|doc|docx|xls|xlsx|csv|zip|rar|txt)$/i;

  if (target) {
    const found = findByFlexibleTarget(target, ["a"]);
    if (found) return found;
  }

  return Array.from(document.querySelectorAll("a"))
    .find((a) => isVisible(a) && (a.hasAttribute("download") || fileExtPattern.test(a.href || ""))) || null;
}

function findScrollableTarget(target) {
  if (!target) return document.body;
  const fromAny = findByFlexibleTarget(target, ["*"]);
  return fromAny || document.body;
}

async function executeSingleAction(action) {
  const actionType = String(action?.type || "").toUpperCase();
  const target = action?.target || "";
  const delayMs = Number(action?.delayMs ?? 500);

  console.log(`Executing action ${actionType} -> ${target || action?.value || ""}`);

  try {
    suppressObserverUntil = Date.now() + Math.max(400, delayMs + 200);

    if (actionType === "TYPE") {
      const element = findInputElement(target);
      if (!element) return { action, status: "error", message: "Input target not found" };

      element.focus();
      element.value = action.value ?? "";
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
      await sleep(delayMs);
      return { action, status: "ok" };
    }

    if (actionType === "CLICK") {
      const element = findClickableElement(target);
      if (!element) return { action, status: "error", message: "Clickable target not found" };

      // Many quiz UIs hide radio inputs and rely on the associated label click.
      if (element.tagName === "INPUT" && ["radio", "checkbox"].includes((element.type || "").toLowerCase())) {
        const forLabel = element.id ? document.querySelector(`label[for="${element.id}"]`) : null;
        if (forLabel && isVisible(forLabel)) {
          forLabel.click();
        } else {
          element.click();
        }
        element.dispatchEvent(new Event("input", { bubbles: true }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
      } else {
        element.click();
      }
      await sleep(delayMs);
      return { action, status: "ok" };
    }

    if (actionType === "SELECT") {
      const element = findSelectElement(target);
      if (!element) return { action, status: "error", message: "Select target not found" };

      const requested = norm(action.value);
      let selectedValue = null;

      for (const option of Array.from(element.options)) {
        const optionValue = norm(option.value);
        const optionText = norm(option.text);
        if (optionValue === requested || optionText === requested) {
          selectedValue = option.value;
          break;
        }
      }

      if (selectedValue === null && action.value != null) {
        element.value = action.value;
      } else if (selectedValue !== null) {
        element.value = selectedValue;
      }

      element.dispatchEvent(new Event("change", { bubbles: true }));
      await sleep(delayMs);
      return { action, status: "ok" };
    }

    if (actionType === "NAVIGATE") {
      const url = action.url || action.value || target;
      if (!url) return { action, status: "error", message: "Missing URL for navigation" };

      window.location.href = url;
      return { action, status: "ok" };
    }

    if (actionType === "DOWNLOAD") {
      const link = findDownloadLink(target);
      if (!link) return { action, status: "error", message: "Download link not found" };

      link.click();
      await sleep(delayMs);
      return { action, status: "ok" };
    }

    if (actionType === "SCROLL") {
      const element = findScrollableTarget(target);
      if (!element) return { action, status: "error", message: "Scroll target not found" };

      element.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(delayMs);
      return { action, status: "ok" };
    }

    return { action, status: "error", message: `Unsupported action type: ${actionType}` };
  } catch (err) {
    return { action, status: "error", message: err?.message || String(err) };
  }
}

async function executeActionPlan(actions = []) {
  const results = [];

  for (const action of actions) {
    const result = await executeSingleAction(action);
    if (result.status === "error") {
      console.error("Action execution failed:", result);
    }
    results.push(result);
  }

  return results;
}

function extractPageContent() {
  const metadata = {
    url: window.location.href,
    title: document.title,
    domain: window.location.hostname,
    meta_description: document.querySelector('meta[name="description"]')?.content || "",
    meta_keywords: document.querySelector('meta[name="keywords"]')?.content || "",
    author: document.querySelector('meta[name="author"]')?.content || document.querySelector('meta[property="article:author"]')?.content || null,
    published_time: document.querySelector('meta[property="article:published_time"]')?.content || document.querySelector('meta[name="date"]')?.content || null
  };

  function detectMainContent() {
    const mainTags = [
      "#mw-content-text",
      ".mw-parser-output",
      "#content",
      "article",
      "main",
      "section",
      "[role='main']",
      "[itemtype*='Article']",
      "[itemtype*='article']"
    ];
    for (const tag of mainTags) {
      const el = document.querySelector(tag);
      if (isVisible(el) && (el.innerText || "").trim().length > 120) {
        return { text: el.innerText, html: el.outerHTML };
      }
    }

    let largestDiv = null;
    let maxLen = 0;
    for (const div of Array.from(document.querySelectorAll("div"))) {
      const length = (div.innerText || "").length;
      if (isVisible(div) && length > maxLen) {
        largestDiv = div;
        maxLen = length;
      }
    }

    if (largestDiv) return { text: largestDiv.innerText, html: largestDiv.outerHTML };
    return { text: document.body.innerText || "", html: document.body.innerHTML || "" };
  }

  // Primary content extraction is used for summary text while full_html is still sent separately.
  const main = detectMainContent();

  const text_content = {
    main_content: main.text || "",
    main_html: main.html || "",
    headings: Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6")).filter(isVisible).map((h) => h.innerText),
    paragraphs: Array.from(document.querySelectorAll("p")).filter(isVisible).map((p) => p.innerText),
    lists: Array.from(document.querySelectorAll("ul,ol")).filter(isVisible).map((list) => list.innerText),
    blockquotes: Array.from(document.querySelectorAll("blockquote")).filter(isVisible).map((bq) => bq.innerText)
  };

  const tables = Array.from(document.querySelectorAll("table")).filter(isVisible).map((table) => {
    const headers = Array.from(table.querySelectorAll("th")).map((th) => th.innerText);
    const rows = Array.from(table.querySelectorAll("tr")).map((tr) => Array.from(tr.querySelectorAll("td")).map((td) => td.innerText));
    return { headers, rows };
  });

  const forms = Array.from(document.querySelectorAll("form")).filter(isVisible).map((form) => ({
    action: form.action,
    method: form.method,
    inputs: Array.from(form.querySelectorAll("input,textarea,select")).filter(isVisible).map((input) => ({
      name: input.name,
      id: input.id,
      placeholder: input.placeholder,
      type: input.type || input.tagName.toLowerCase()
    }))
  }));

  const buttons = Array.from(document.querySelectorAll("button")).filter(isVisible).map((btn) => btn.innerText);

  const selects = Array.from(document.querySelectorAll("select")).filter(isVisible).map((sel) => ({
    name: sel.name,
    id: sel.id,
    options: Array.from(sel.options).map((opt) => opt.value)
  }));

  const links = Array.from(document.querySelectorAll("a")).filter(isVisible).map((a) => ({
    text: a.innerText,
    href: a.href,
    internal: a.href.startsWith(window.location.origin)
  }));

  const navigation = {
    internal_links: links.filter((l) => l.internal),
    external_links: links.filter((l) => !l.internal)
  };

  const media = {
    images: Array.from(document.querySelectorAll("img")).filter(isVisible).map((img) => ({ src: img.src, alt: img.alt })),
    videos: Array.from(document.querySelectorAll("video")).filter(isVisible).map((video) => ({ src: video.src, poster: video.poster })),
    iframes: Array.from(document.querySelectorAll("iframe")).filter(isVisible).map((iframe) => ({ src: iframe.src }))
  };

  function buildUniqueSelector(el) {
    if (!el) return "";
    if (el.id) return `#${el.id}`;
    const name = el.getAttribute("name");
    if (name) return `${el.tagName.toLowerCase()}[name="${name}"]`;
    const testId = el.getAttribute("data-testid");
    if (testId) return `${el.tagName.toLowerCase()}[data-testid="${testId}"]`;
    return el.tagName.toLowerCase();
  }

  function detectQuizData() {
    const questions = [];

    const containers = Array.from(document.querySelectorAll("fieldset, [role='radiogroup'], .question, .quiz-question, .assessment-question"));

    for (const container of containers) {
      if (!isVisible(container)) continue;
      const optionLabels = Array.from(container.querySelectorAll("label"))
        .filter(isVisible)
        .map((label) => {
          const input = label.querySelector("input[type='radio'], input[type='checkbox']");
          return {
            text: (label.innerText || "").trim(),
            input_id: input?.id || null,
            input_name: input?.name || null,
            input_value: input?.value || null,
            selector: buildUniqueSelector(input || label)
          };
        })
        .filter((opt) => opt.text);

      if (!optionLabels.length) continue;

      const heading = container.querySelector("h1,h2,h3,h4,h5,h6,legend,.question-title,.prompt");
      const questionText = (heading?.innerText || container.innerText || "").split("\n")[0].trim();

      questions.push({
        question_text: questionText,
        options: optionLabels
      });
    }

    // Fallback grouping for quiz UIs without explicit question containers.
    if (questions.length === 0) {
      const radioLike = Array.from(document.querySelectorAll("input[type='radio'], input[type='checkbox']"));
      const groups = new Map();

      for (const input of radioLike) {
        const key = input.name || input.id || `group-${groups.size + 1}`;
        if (!groups.has(key)) groups.set(key, []);

        const explicitLabel = input.id ? document.querySelector(`label[for="${input.id}"]`) : null;
        const parentLabel = input.closest("label");
        const label = explicitLabel || parentLabel;

        groups.get(key).push({
          text: (label?.innerText || input.value || "").trim(),
          input_id: input.id || null,
          input_name: input.name || null,
          input_value: input.value || null,
          selector: buildUniqueSelector(input)
        });
      }

      for (const [groupName, opts] of groups.entries()) {
        const cleanOpts = opts.filter((o) => o.text);
        if (!cleanOpts.length) continue;
        questions.push({
          question_text: String(groupName),
          options: cleanOpts
        });
      }
    }

    const submitCandidates = Array.from(document.querySelectorAll("button, input[type='submit'], a"))
      .filter(isVisible)
      .map((el) => ({
        text: (el.innerText || el.value || "").trim(),
        id: el.id || null,
        selector: buildUniqueSelector(el)
      }))
      .filter((btn) => /submit|finish|next|check|continue|done/i.test(btn.text));

    return {
      question_count: questions.length,
      questions,
      submit_candidates: submitCandidates
    };
  }

  function detectDocuments() {
    const detected = [];
    const toLower = (value) => String(value || "").toLowerCase();

    document.querySelectorAll("embed,object,iframe").forEach((el) => {
      const src = el.src || el.data;
      const low = toLower(src);
      if (low.endsWith(".pdf")) detected.push({ type: "embedded_pdf", src });
    });

    document.querySelectorAll("a").forEach((a) => {
      const href = a.href;
      const low = toLower(href);
      if (!href) return;
      if (low.endsWith(".pdf")) detected.push({ type: "pdf_link", href });
      if (low.endsWith(".xml")) detected.push({ type: "xml_link", href });
      if (low.endsWith(".csv")) detected.push({ type: "csv_link", href });
      if (low.endsWith(".docx")) detected.push({ type: "docx_link", href });
    });

    return detected;
  }

  return {
    metadata,
    text_content,
    tables,
    forms,
    buttons,
    selects,
    navigation,
    media,
    full_text: document.body?.innerText || "",
    full_html: document.documentElement?.outerHTML || "",
    quiz_data: detectQuizData(),
    detected_documents: detectDocuments(),
    dom_map: generateDOMTreeMap()
  };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("Content script received message:", request?.action || request);

  if (request.action === "extractPageContent") {
    const run = () => {
      try {
        const data = extractPageContent();
        sendResponse({ data });
      } catch (err) {
        sendResponse({ error: "Scraping error: " + (err.message || String(err)) });
      }
    };

    if (document.readyState !== "complete") {
      window.addEventListener("load", run, { once: true });
    } else {
      run();
    }
    return true;
  }

  if (request.action === "getDomMap") {
    waitForDomReady().then(() => {
      try {
        sendResponse({ dom_map: generateDOMMap() });
      } catch (err) {
        sendResponse({ error: "DOM map error: " + (err.message || String(err)) });
      }
    });
    return true;
  }

  if (request.action === "applyAutoAssist") {
    autoAssistState.enabled = Boolean(request.enabled);
    autoAssistState.autofillEnabled = typeof request.autofillEnabled === "boolean" ? request.autofillEnabled : true;
    autoAssistState.profile = request.profile && typeof request.profile === "object" ? request.profile : {};
    autoAssistState.credentials = request.credentials && typeof request.credentials === "object" ? request.credentials : null;
    const filled = applyAutofillToPage();
    sendResponse({ ok: true, filled });
    return true;
  }

  if (request.action === "showSummaryOverlay") {
    showSummaryOverlay(request.summary || "");
    sendResponse({ ok: true });
    return true;
  }

  if (request.action === "startContinuousObservation") {
    startContinuousObservation(request.config || {});
    sendResponse({ ok: true, enabled: true });
    return true;
  }

  if (request.action === "stopContinuousObservation") {
    stopContinuousObservation();
    sendResponse({ ok: true, enabled: false });
    return true;
  }

  if (request.action === "executeActionPlan") {
    (async () => {
      try {
        const results = await executeActionPlan(request.actions || []);
        const failures = results.filter((r) => r.status !== "ok");
        sendResponse({
          ok: failures.length === 0,
          message: failures.length === 0
            ? "Automation executed successfully"
            : `Automation finished with ${failures.length} failed action(s)` ,
          results
        });
      } catch (err) {
        sendResponse({ error: "Execution error: " + (err.message || String(err)) });
      }
    })();
    return true;
  }

  if (request.action === "validateActionPlan") {
    (async () => {
      try {
        const actions = request.actions || [];
        const validations = [];
        for (const action of actions) {
          const type = String(action?.type || "").toUpperCase();
          const target = action?.target || action?.url || action?.value || "";
          let ok = false;
          let reason = null;

          try {
            if (type === "NAVIGATE") {
              ok = !!action.url || !!action.value || !!action.target;
            } else if (type === "TYPE") {
              const el = findInputElement(target);
              ok = !!el;
              if (!ok) reason = "input not found";
            } else if (type === "CLICK") {
              const el = findClickableElement(target);
              ok = !!el;
              if (!ok) reason = "clickable element not found";
            } else if (type === "SELECT") {
              const el = findSelectElement(target);
              ok = !!el;
              if (!ok) reason = "select element not found";
            } else if (type === "SCROLL") {
              ok = true; // scroll target can default to body
            } else {
              // unknown action types are considered not valid for execution
              ok = false;
              reason = `unsupported action type: ${type}`;
            }
          } catch (err) {
            ok = false;
            reason = err?.message || String(err);
          }

          validations.push({ action, ok, reason });
        }

        sendResponse({ ok: true, validations });
      } catch (err) {
        sendResponse({ ok: false, error: err?.message || String(err) });
      }
    })();
    return true;
  }
});
