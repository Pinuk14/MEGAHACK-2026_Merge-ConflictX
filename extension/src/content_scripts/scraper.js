// Utility: Checks if an element is visible
function isVisible(elem) {
  const style = window.getComputedStyle(elem);
  return style.display !== "none" && style.visibility !== "hidden" && elem.offsetParent !== null;
}

// Utility: Generates a DOM map (tree structure)
function generateDOMTreeMap(node = document.body) {
  const map = {
    tag: node.tagName,
    children: []
  };
  for (let child of node.children) {
    map.children.push(generateDOMTreeMap(child));
  }
  return map;
}

// DOM interaction map for automation planning
function generateDOMMap() {
  const inputs = Array.from(document.querySelectorAll("input,textarea"))
    .filter(isVisible).map(input => ({
      id: input.id || "",
      name: input.name || "",
      type: input.type || input.tagName.toLowerCase(),
      placeholder: input.placeholder || "",
      label: document.querySelector(`label[for="${input.id}"]`)?.innerText || ""
    }));

  const buttons = Array.from(document.querySelectorAll("button,input[type='button'],input[type='submit']"))
    .filter(isVisible).map(btn => ({
      id: btn.id || "",
      text: (btn.innerText || btn.value || "").trim(),
      class: btn.className || ""
    }));

  const forms = Array.from(document.querySelectorAll("form"))
    .filter(isVisible).map(form => ({
      id: form.id || "",
      action: form.action || ""
    }));

  const links = Array.from(document.querySelectorAll("a"))
    .filter(isVisible).map(link => ({
      href: link.href || "",
      text: (link.innerText || "").trim()
    }));

  return { inputs, buttons, forms, links };
}

function waitForDomReady() {
  return new Promise(resolve => {
    if (document.readyState === "complete") {
      resolve();
      return;
    }
    window.addEventListener("load", () => resolve(), { once: true });
  });
}

function findElementByTarget(target) {
  if (!target) return null;
  const byId = document.getElementById(target);
  if (byId) return byId;
  const byName = document.querySelector(`[name="${CSS.escape(target)}"]`);
  if (byName) return byName;
  const byTestId = document.querySelector(`[data-testid="${CSS.escape(target)}"]`);
  if (byTestId) return byTestId;
  const byText = Array.from(document.querySelectorAll("button,a")).find(el =>
    (el.innerText || "").trim().toLowerCase() === target.toLowerCase()
  );
  return byText || null;
}

function executeActionPlan(actions = []) {
  const results = [];

  actions.forEach(action => {
    try {
      console.log(`Executing action: ${action.type} -> ${action.target || action.value || ""}`);

      if (action.type === "NAVIGATE") {
        const url = action.url || action.target;
        if (url) {
          window.location.href = url;
          results.push({ action, status: "ok" });
        } else {
          results.push({ action, status: "error", message: "Missing URL" });
        }
        return;
      }

      const element = findElementByTarget(action.target);
      if (!element) {
        console.warn("Target not found:", action.target);
        results.push({ action, status: "error", message: "Target not found" });
        return;
      }

      if (action.type === "TYPE") {
        element.focus();
        element.value = action.value ?? "";
        element.dispatchEvent(new Event("input", { bubbles: true }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
        results.push({ action, status: "ok" });
        return;
      }

      if (action.type === "SELECT") {
        element.value = action.value ?? "";
        element.dispatchEvent(new Event("change", { bubbles: true }));
        results.push({ action, status: "ok" });
        return;
      }

      if (action.type === "CLICK") {
        element.click();
        results.push({ action, status: "ok" });
        return;
      }

      results.push({ action, status: "error", message: "Unsupported action type" });
    } catch (err) {
      results.push({ action, status: "error", message: err.message });
    }
  });

  return results;
}

// Main extraction function
function extractPageContent() {
  // --- Metadata ---
  const metadata = {
    url: window.location.href,
    title: document.title,
    domain: window.location.hostname,
    meta_description: document.querySelector('meta[name="description"]')?.content || "",
    meta_keywords: document.querySelector('meta[name="keywords"]')?.content || ""
  };

  // --- Main Content ---
  // Try to detect main content
  function detect_main_content() {
    const mainTags = ["article", "main", "section"];
    for (let tag of mainTags) {
      const el = document.querySelector(tag);
      if (el && isVisible(el)) return el.innerText;
    }
    // Fallback: largest visible div
    let largestDiv = null, maxLen = 0;
    document.querySelectorAll("div").forEach(div => {
      if (isVisible(div) && div.innerText.length > maxLen) {
        largestDiv = div;
        maxLen = div.innerText.length;
      }
    });
    if (largestDiv) return largestDiv.innerText;
    // Fallback: document.body
    return document.body.innerText;
  }

  const text_content = {
    main_content: detect_main_content(),
    headings: Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
      .filter(isVisible).map(h => h.innerText),
    paragraphs: Array.from(document.querySelectorAll("p"))
      .filter(isVisible).map(p => p.innerText),
    lists: Array.from(document.querySelectorAll("ul,ol"))
      .filter(isVisible).map(list => list.innerText),
    blockquotes: Array.from(document.querySelectorAll("blockquote"))
      .filter(isVisible).map(bq => bq.innerText)
  };

  // --- Structured Elements ---
  const tables = Array.from(document.querySelectorAll("table"))
    .filter(isVisible).map(table => {
      const headers = Array.from(table.querySelectorAll("th")).map(th => th.innerText);
      const rows = Array.from(table.querySelectorAll("tr")).map(tr =>
        Array.from(tr.querySelectorAll("td")).map(td => td.innerText)
      );
      return { headers, rows };
    });

  const forms = Array.from(document.querySelectorAll("form"))
    .filter(isVisible).map(form => ({
      action: form.action,
      method: form.method,
      inputs: Array.from(form.querySelectorAll("input,textarea,select"))
        .filter(isVisible).map(input => ({
          name: input.name,
          id: input.id,
          placeholder: input.placeholder,
          type: input.type || input.tagName.toLowerCase()
        }))
    }));

  const buttons = Array.from(document.querySelectorAll("button"))
    .filter(isVisible).map(btn => btn.innerText);

  const selects = Array.from(document.querySelectorAll("select"))
    .filter(isVisible).map(sel => ({
      name: sel.name,
      id: sel.id,
      options: Array.from(sel.options).map(opt => opt.value)
    }));

  // --- Navigation ---
  const links = Array.from(document.querySelectorAll("a"))
    .filter(isVisible).map(a => ({
      text: a.innerText,
      href: a.href,
      internal: a.href.startsWith(window.location.origin)
    }));

  const navigation = {
    internal_links: links.filter(l => l.internal),
    external_links: links.filter(l => !l.internal)
  };

  // --- Media ---
  const images = Array.from(document.querySelectorAll("img"))
    .filter(isVisible).map(img => ({
      src: img.src,
      alt: img.alt
    }));

  const videos = Array.from(document.querySelectorAll("video"))
    .filter(isVisible).map(video => ({
      src: video.src,
      poster: video.poster
    }));

  const iframes = Array.from(document.querySelectorAll("iframe"))
    .filter(isVisible).map(iframe => ({
      src: iframe.src
    }));

  const media = { images, videos, iframes };

  // --- Document Detection ---
  function detectDocuments() {
    const detected = [];
    // Embedded PDFs
    document.querySelectorAll("embed,object,iframe").forEach(el => {
      const src = el.src || el.data;
      if (src && src.endsWith(".pdf")) detected.push({ type: "embedded_pdf", src });
    });
    // Downloadable links
    document.querySelectorAll("a").forEach(a => {
      const href = a.href;
      if (href) {
        if (href.endsWith(".pdf")) detected.push({ type: "pdf_link", href });
        if (href.endsWith(".xml")) detected.push({ type: "xml_link", href });
        if (href.endsWith(".csv")) detected.push({ type: "csv_link", href });
        if (href.endsWith(".docx")) detected.push({ type: "docx_link", href });
      }
    });
    return detected;
  }

  // --- DOM Map ---
  const dom_map = generateDOMTreeMap();

  return {
    metadata,
    text_content,
    tables,
    forms,
    buttons,
    selects,
    navigation,
    media,
    detected_documents: detectDocuments(),
    dom_map
  };
}

// Listen for messages from background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "extractPageContent") {
    // Wait for DOM ready
    if (document.readyState !== "complete") {
      window.addEventListener("load", () => {
        try {
          const data = extractPageContent();
          sendResponse({ data });
        } catch (err) {
          sendResponse({ error: "Scraping error: " + err.message });
        }
      });
      return true;
    } else {
      try {
        const data = extractPageContent();
        sendResponse({ data });
      } catch (err) {
        sendResponse({ error: "Scraping error: " + err.message });
      }
      return true;
    }
  }

  if (request.action === "getDomMap") {
    waitForDomReady().then(() => {
      try {
        const domMap = generateDOMMap();
        sendResponse({ dom_map: domMap });
      } catch (err) {
        sendResponse({ error: "DOM map error: " + err.message });
      }
    });
    return true;
  }

  if (request.action === "executeActionPlan") {
    try {
      const results = executeActionPlan(request.actions || []);
      sendResponse({ results });
    } catch (err) {
      sendResponse({ error: "Execution error: " + err.message });
    }
    return true;
  }
});