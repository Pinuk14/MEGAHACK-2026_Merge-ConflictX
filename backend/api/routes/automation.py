from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.services.ollama_service import OllamaService
from backend.app.services.scrape_memory_service import ScrapeMemoryService

router = APIRouter(tags=["automation"])
_ollama = OllamaService()
_memory = ScrapeMemoryService(project_root=Path(__file__).resolve().parents[3])


def _write_automation_log(entry: Dict[str, Any]) -> None:
    try:
        base = os.getcwd()
        log_dir = os.path.join(base, "backend")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "automation_debug.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return


class AutomationPlanRequest(BaseModel):
    query: str = Field(..., min_length=2, description="User automation request")
    url: Optional[str] = Field(default=None, description="Current page URL")
    dom_map: Dict[str, Any] = Field(default_factory=dict, description="DOM map extracted by extension")
    full_html: Optional[str] = Field(default=None, description="Full page HTML when provided by the extension")


class AutomationAction(BaseModel):
    type: str
    target: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    delayMs: int = 500


class AutomationPlanResponse(BaseModel):
    actions: List[AutomationAction]


class QuizSolveRequest(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    full_text: Optional[str] = None
    analysis_summary: Optional[Dict[str, Any]] = None
    quiz_data: Dict[str, Any] = Field(default_factory=dict)
    full_html: Optional[str] = None


class QuizSolveResponse(BaseModel):
    answers: List[Dict[str, Any]]
    actions: List[AutomationAction]


class AgentLoopEvent(BaseModel):
    ts: Optional[int] = None
    type: str
    url: Optional[str] = None
    title: Optional[str] = None
    element: Optional[Dict[str, Any]] = None
    page_signals: Optional[Dict[str, Any]] = None
    value_length: Optional[int] = None
    y: Optional[int] = None
    x: Optional[int] = None
    added_nodes: Optional[int] = None


class AgentLoopTickRequest(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    events: List[AgentLoopEvent] = Field(default_factory=list)
    dom_map: Dict[str, Any] = Field(default_factory=dict)
    user_memory: Dict[str, Any] = Field(default_factory=dict)


class AgentLoopTickResponse(BaseModel):
    actions: List[AutomationAction] = Field(default_factory=list)
    reason: str = ""


ALLOWED_ACTIONS = {"TYPE", "CLICK", "SELECT", "NAVIGATE", "DOWNLOAD", "SCROLL"}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _clean_html_preview(html: Optional[str], limit: int = 12000) -> str:
    if not html:
        return ""
    try:
        cleaned = re.sub(r"(?s)<(script|style)[^>]*>.*?</\\1>", " ", html, flags=re.IGNORECASE)
        cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.S)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:limit]
    except Exception:
        return (html or "")[:limit]


def _extract_value_after_keywords(query: str, keywords: List[str]) -> Optional[str]:
    q = _normalize(query)
    for kw in keywords:
        pattern = rf"{kw}\s+(?:as|to|with)?\s*([a-z0-9_\- ]{{2,}})"
        m = re.search(pattern, q)
        if m:
            return m.group(1).strip()
    return None


def _best_input_target(dom_map: Dict[str, Any], query: str) -> Optional[str]:
    q = _normalize(query)
    candidates = dom_map.get("inputs") or []
    if not isinstance(candidates, list):
        return None

    best = None
    best_score = -1

    for item in candidates:
        if not isinstance(item, dict):
            continue
        fields = [
            str(item.get("id") or ""),
            str(item.get("name") or ""),
            str(item.get("placeholder") or ""),
            str(item.get("label") or ""),
        ]
        score = 0
        for f in fields:
            nf = _normalize(f)
            if not nf:
                continue
            if nf in q:
                score += 4
            for token in nf.split(" "):
                if token and token in q:
                    score += 1
        if score > best_score:
            best_score = score
            best = item

    if not best:
        return None

    return best.get("id") or best.get("name") or best.get("placeholder") or None


def _best_button_target(dom_map: Dict[str, Any], query: str) -> Optional[str]:
    q = _normalize(query)
    candidates = dom_map.get("buttons") or []
    if not isinstance(candidates, list):
        return None

    best = None
    best_score = -1

    for item in candidates:
        if not isinstance(item, dict):
            continue
        fields = [str(item.get("id") or ""), str(item.get("text") or "")]
        score = 0
        for f in fields:
            nf = _normalize(f)
            if not nf:
                continue
            if nf in q:
                score += 4
            for token in nf.split(" "):
                if token and token in q:
                    score += 1
        if score > best_score:
            best_score = score
            best = item

    if not best:
        return None

    return best.get("id") or best.get("text") or None


def _best_link_target(dom_map: Dict[str, Any], query: str) -> Optional[str]:
    q = _normalize(query)
    candidates = dom_map.get("links") or []
    if not isinstance(candidates, list):
        return None

    for item in candidates:
        if not isinstance(item, dict):
            continue
        href = _normalize(str(item.get("href") or ""))
        text = _normalize(str(item.get("text") or ""))
        if any(word in href for word in ["pdf", "download", "policy", "doc", "document"]):
            return item.get("href") or item.get("text") or None
        if text and text in q:
            return item.get("text") or item.get("href") or None
    return None


def _extract_navigation_url(query: str) -> Optional[str]:
    m = re.search(r"(https?://[^\s]+)", query, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _build_plan(query: str, dom_map: Dict[str, Any]) -> List[AutomationAction]:
    q = _normalize(query)
    actions: List[AutomationAction] = []

    wants_fill = any(k in q for k in ["fill", "enter", "type", "input"])
    wants_submit = any(k in q for k in ["submit", "send", "login", "click"])
    wants_select = any(k in q for k in ["select", "choose", "pick"])
    wants_nav = any(k in q for k in ["navigate", "go to", "open"]) and ("http" in q or "section" in q)
    wants_download = any(k in q for k in ["download", "save file", "policy document", "document"])
    wants_scroll = any(k in q for k in ["scroll", "go down", "move to section"])

    if wants_fill:
      target = _best_input_target(dom_map, q)
      value = _extract_value_after_keywords(q, ["enter", "type", "fill", "input"]) or ""
      if target:
          actions.append(AutomationAction(type="TYPE", target=target, value=value, delayMs=500))

    if wants_select:
      target = _best_input_target(dom_map, q)
      value = _extract_value_after_keywords(q, ["select", "choose", "pick"])
      if target and value:
          actions.append(AutomationAction(type="SELECT", target=target, value=value, delayMs=500))

    if wants_download:
      link_target = _best_link_target(dom_map, q)
      actions.append(AutomationAction(type="DOWNLOAD", target=link_target, delayMs=500))

    if wants_scroll:
      actions.append(AutomationAction(type="SCROLL", target="main", delayMs=500))

    if wants_nav:
      nav_url = _extract_navigation_url(query)
      if nav_url:
          actions.append(AutomationAction(type="NAVIGATE", url=nav_url, delayMs=500))
      else:
          section_target = _extract_value_after_keywords(q, ["to", "section"])
          actions.append(AutomationAction(type="SCROLL", target=section_target or "main", delayMs=500))

    if wants_submit:
      click_target = _best_button_target(dom_map, q) or "submit"
      actions.append(AutomationAction(type="CLICK", target=click_target, delayMs=500))

    if not actions:
      fallback_click = _best_button_target(dom_map, q)
      if fallback_click:
          actions.append(AutomationAction(type="CLICK", target=fallback_click, delayMs=500))

    return actions


def _compact_dom_map(dom_map: Dict[str, Any], limit: int = 40) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for key in ["inputs", "buttons", "forms", "links"]:
        items = dom_map.get(key) or []
        if isinstance(items, list):
            compact[key] = items[:limit]
    return compact


def _validate_and_cast_actions(actions_raw: Any) -> List[AutomationAction]:
    if not isinstance(actions_raw, list):
        return []

    def _as_optional_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        return None

    cleaned: List[AutomationAction] = []
    for action in actions_raw:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type") or "").upper().strip()
        if action_type not in ALLOWED_ACTIONS:
            continue

        delay = action.get("delayMs", 500)
        try:
            delay = int(delay)
        except Exception:
            delay = 500
        delay = max(100, min(delay, 5000))

        try:
            cleaned.append(
                AutomationAction(
                    type=action_type,
                    target=_as_optional_str(action.get("target")),
                    value=_as_optional_str(action.get("value")),
                    url=_as_optional_str(action.get("url")),
                    delayMs=delay,
                )
            )
        except Exception:
            continue

    return cleaned


def _llm_automation_plan(query: str, url: Optional[str], dom_map: Dict[str, Any], memory_context: Optional[Dict[str, Any]] = None) -> List[AutomationAction]:
    system_prompt = (
        "You are a browser automation planner. "
        "Given a user query and DOM map, output only JSON with this schema: "
        "{\"actions\":[{\"type\":\"TYPE|CLICK|SELECT|NAVIGATE|DOWNLOAD|SCROLL\",\"target\":string|null,\"value\":string|null,\"url\":string|null,\"delayMs\":number}]}. "
        "Only include actions that can be executed in a browser extension content script."
    )

    # include a compact DOM map and optionally some page HTML context (truncated)
    compact = _compact_dom_map(dom_map)
    user_payload = {
        "query": query,
        "url": url,
        "dom_map": compact,
        "memory_context": memory_context or {},
    }
    # If caller provided `full_html` inside dom_map (rare) use it; else leave out to avoid massive prompts
    if isinstance(dom_map, dict) and dom_map.get("full_html"):
        html_preview = _clean_html_preview(dom_map.get("full_html"), limit=12000)
        user_payload["html_preview"] = html_preview

    user_prompt = json.dumps(user_payload, ensure_ascii=False)

    raw = _ollama.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
    if not raw:
        return []

    actions = _validate_and_cast_actions(raw.get("actions"))
    if actions:
        return actions

    # Repair pass if first response is malformed/empty
    repair_prompt = (
        "Your previous output was invalid. Return ONLY valid JSON with key `actions` as a list. "
        "Use supported types: TYPE, CLICK, SELECT, NAVIGATE, DOWNLOAD, SCROLL."
    )
    repair_raw = _ollama.generate_json(system_prompt=system_prompt, user_prompt=f"{repair_prompt}\n\n{user_prompt}")
    if not repair_raw:
        return []
    return _validate_and_cast_actions(repair_raw.get("actions"))


def _llm_quiz_answers(request: QuizSolveRequest, memory_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    quiz_data = request.quiz_data or {}
    questions = quiz_data.get("questions") or []
    if not isinstance(questions, list) or not questions:
        return []

    minimal_questions = []
    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            continue
        opts = q.get("options") or []
        minimal_questions.append(
            {
                "question_index": idx,
                "question_text": q.get("question_text"),
                "options": [o.get("text") for o in opts if isinstance(o, dict)],
            }
        )

    system_prompt = (
        "You are a quiz-solving assistant. "
        "Use context (URL/title/summary) to pick the most likely correct option for each question. "
        "Return only JSON with schema: {\"answers\":[{\"question_index\":number,\"selected_option_text\":string,\"reason\":string}]}."
    )

    user_prompt = json.dumps(
        {
            "url": request.url,
            "title": request.title,
            "summary": request.analysis_summary,
            "full_html": request.full_html or "",
            "questions": minimal_questions,
            "memory_context": memory_context or {},
            "instruction": "Use complete HTML and choose only options that are explicitly present in the page/question context.",
        },
        ensure_ascii=False,
    )

    raw = _ollama.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
    if not raw:
        return []
    answers = raw.get("answers")
    if not isinstance(answers, list) or not answers:
        return []

    # Reliability pass: ask model to review and correct answer set for consistency.
    review_system = (
        "You are reviewing quiz answers for consistency. "
        "Return ONLY JSON: {\"answers\":[{\"question_index\":number,\"selected_option_text\":string,\"reason\":string}]}."
    )
    review_user = json.dumps(
        {
            "questions": minimal_questions,
            "draft_answers": answers,
            "instruction": "Fix mismatches where selected option text does not exist in options. Keep question_index intact.",
        },
        ensure_ascii=False,
    )
    reviewed = _ollama.generate_json(system_prompt=review_system, user_prompt=review_user)
    if reviewed and isinstance(reviewed.get("answers"), list) and reviewed.get("answers"):
        return reviewed.get("answers")

    return answers


def _llm_verify_quiz_answers_against_html(
    request: QuizSolveRequest,
    draft_answers: List[Dict[str, Any]],
    memory_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not draft_answers:
        return []

    questions = (request.quiz_data or {}).get("questions") or []
    if not isinstance(questions, list) or not questions:
        return draft_answers

    minimal_questions = []
    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            continue
        opts = q.get("options") or []
        minimal_questions.append(
            {
                "question_index": idx,
                "question_text": q.get("question_text"),
                "options": [o.get("text") for o in opts if isinstance(o, dict)],
            }
        )

    system_prompt = (
        "You validate quiz answers against HTML and question options. "
        "Correct any unsupported answer. "
        "Return ONLY JSON: {\"answers\":[{\"question_index\":number,\"selected_option_text\":string,\"reason\":string}]}."
    )
    user_prompt = json.dumps(
        {
            "url": request.url,
            "title": request.title,
            "full_html": request.full_html or "",
            "questions": minimal_questions,
            "draft_answers": draft_answers,
            "memory_context": memory_context or {},
            "rule": "Selected option text must exist in each question's options and be supported by page content.",
        },
        ensure_ascii=False,
    )

    verified = _ollama.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
    if verified and isinstance(verified.get("answers"), list) and verified.get("answers"):
        return verified.get("answers")
    return draft_answers


def _llm_extract_quiz_from_html(full_html: Optional[str], memory_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Ask the LLM to extract quiz structure from raw page HTML.

    Returns a dict: {question_count, questions:[{question_text, options:[{text}]}], submit_candidates:[{text}]}
    """
    if not full_html:
        return {}

    system = (
        "You are an HTML analyzer. Given the complete page HTML, extract any quiz/assessment questions. "
        "Return ONLY valid JSON with schema: {\"question_count\": number, \"questions\": [{\"question_text\": string, \"options\": [{\"text\": string}] }], \"submit_candidates\": [{\"text\": string}] }. "
        "Do not include any extra text."
    )

    user = json.dumps({"full_html": full_html or "", "memory_context": memory_context or {}}, ensure_ascii=False)
    raw = _ollama.generate_json(system_prompt=system, user_prompt=user)
    if not raw:
        return {}

    # Basic validation/shape enforcement
    qc = raw.get("question_count") or (len(raw.get("questions") or []) if isinstance(raw.get("questions"), list) else 0)
    questions = raw.get("questions") or []
    submit = raw.get("submit_candidates") or []
    return {"question_count": qc, "questions": questions, "submit_candidates": submit}


def _answers_to_actions(quiz_data: Dict[str, Any], llm_answers: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[AutomationAction]]:
    questions = quiz_data.get("questions") or []
    submit_candidates = quiz_data.get("submit_candidates") or []
    if not isinstance(questions, list):
        questions = []

    answers_out: List[Dict[str, Any]] = []
    actions: List[AutomationAction] = []

    # quick lookup by index
    answer_by_index: Dict[int, Dict[str, Any]] = {}
    for item in llm_answers:
        if not isinstance(item, dict):
            continue
        idx = item.get("question_index")
        if isinstance(idx, int):
            answer_by_index[idx] = item

    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            continue
        options = q.get("options") or []
        if not isinstance(options, list) or not options:
            continue

        picked_text = ""
        if idx in answer_by_index:
            picked_text = str(answer_by_index[idx].get("selected_option_text") or "")

        best = None
        if picked_text:
            picked_norm = _normalize(picked_text)
            for opt in options:
                if not isinstance(opt, dict):
                    continue
                opt_text = str(opt.get("text") or "")
                if _normalize(opt_text) == picked_norm or picked_norm in _normalize(opt_text):
                    best = opt
                    break

        if best is None:
            # Strict LLM mode: never guess by picking a default option.
            continue

        if not best:
            continue

        target = best.get("input_id") or best.get("selector") or best.get("text")
        answers_out.append(
            {
                "question_index": idx,
                "question_text": q.get("question_text"),
                "selected_option_text": best.get("text"),
                "selected_target": target,
            }
        )
        if target:
            actions.append(AutomationAction(type="CLICK", target=str(target), delayMs=400))

    # Safety guard: click submit only if at least one answer action exists.
    if actions and isinstance(submit_candidates, list) and submit_candidates:
        submit = submit_candidates[0] if isinstance(submit_candidates[0], dict) else {}
        submit_target = submit.get("id") or submit.get("selector") or submit.get("text")
        if submit_target:
            actions.append(AutomationAction(type="CLICK", target=str(submit_target), delayMs=700))

    return answers_out, actions


def _loop_event_query(events: List[AgentLoopEvent]) -> str:
    if not events:
        return "Observe current page and assist with user task"
    parts: List[str] = []
    for event in events[-6:]:
        etype = str(event.type or "").upper()
        if etype in {"FOCUS", "INPUT", "CLICK"}:
            el = event.element or {}
            text = str(el.get("text") or el.get("placeholder") or el.get("name") or el.get("id") or "")
            parts.append(f"{etype}:{text}")
        elif etype == "SCROLL":
            parts.append(f"SCROLL:{event.y or 0}")
        elif etype == "DOM_MUTATION":
            parts.append("DOM_MUTATION")
        elif etype == "PAGE_OBSERVED":
            parts.append("PAGE_OBSERVED")
    return " | ".join(parts) or "Assist on current page"


def _extract_known_form_values(user_memory: Dict[str, Any]) -> Dict[str, str]:
    profile = user_memory.get("profile") if isinstance(user_memory, dict) else {}
    creds = user_memory.get("site_credentials") if isinstance(user_memory, dict) else {}
    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(creds, dict):
        creds = {}
    return {
        "name": str(profile.get("name") or ""),
        "email": str(creds.get("email") or profile.get("email") or ""),
        "phone": str(profile.get("phone") or ""),
        "address": str(profile.get("address") or ""),
        "username": str(creds.get("username") or creds.get("email") or profile.get("email") or ""),
        "password": str(creds.get("password") or ""),
    }


def _loop_fallback_actions(request: AgentLoopTickRequest) -> Tuple[List[AutomationAction], str]:
    events = request.events or []
    dom_map = request.dom_map or {}
    known = _extract_known_form_values(request.user_memory or {})

    # If user focused input fields recently, prioritize filling known values.
    recent_focus_or_input = [
        e for e in events[-5:]
        if str(e.type or "").upper() in {"FOCUS", "INPUT"}
    ]
    if recent_focus_or_input:
        actions: List[AutomationAction] = []
        inputs = dom_map.get("inputs") or []
        for inp in inputs[:8]:
            if not isinstance(inp, dict):
                continue
            hay = " ".join([
                str(inp.get("id") or ""),
                str(inp.get("name") or ""),
                str(inp.get("placeholder") or ""),
                str(inp.get("label") or ""),
                str(inp.get("type") or ""),
            ]).lower()
            value = ""
            if "password" in hay:
                value = known.get("password") or ""
            elif "email" in hay:
                value = known.get("email") or ""
            elif any(k in hay for k in ["phone", "mobile", "tel"]):
                value = known.get("phone") or ""
            elif any(k in hay for k in ["user", "login"]):
                value = known.get("username") or ""
            elif "address" in hay:
                value = known.get("address") or ""
            elif "name" in hay:
                value = known.get("name") or ""

            target = inp.get("id") or inp.get("name") or inp.get("placeholder")
            if target and value:
                actions.append(AutomationAction(type="TYPE", target=str(target), value=value, delayMs=300))

        if actions:
            return actions[:4], "Filled likely form fields from user memory"

    # Reading scenario: if mostly scrolling article-like page, no direct action needed here.
    recent_scrolls = [e for e in events[-6:] if str(e.type or "").upper() == "SCROLL"]
    page_type = ((events[-1].page_signals or {}).get("page_type") if events else None) or ""
    if recent_scrolls and str(page_type).lower() == "article":
        return [], "Reading detected; summary assistance handled by analyze flow"

    return [], "No safe autonomous action identified"


@router.post("/automation_plan", response_model=AutomationPlanResponse)
def automation_plan(request: AutomationPlanRequest) -> AutomationPlanResponse:
    # 1) Try LLM planner (Ollama), 2) fallback to deterministic planner
    dom_map = request.dom_map or {}
    if request.full_html:
        dom_map = dict(dom_map)
        dom_map["full_html"] = request.full_html

    current_scraped = {
        "url": request.url,
        "dom_map": request.dom_map or {},
        "full_html": request.full_html,
    }
    memory_ctx = _memory.memory_context(request.url, current_scraped)
    memory_write = _memory.remember_scrape(request.url or "", current_scraped) if request.url else {
        "saved": False,
        "reason": "missing_url",
    }

    # call LLM planner and record whether it returned anything
    llm_called = True
    llm_actions = _llm_automation_plan(request.query, request.url, dom_map or {}, memory_context=memory_ctx)
    actions = llm_actions or []
    if not actions:
        actions = _build_plan(request.query, request.dom_map or {})

    # If still no actions, attempt quiz extraction+solve when page looks like a quiz
    quiz_attempted = False
    quiz_actions_count = 0
    try:
        if not actions:
            looks_like_quiz = False
            inputs = (request.dom_map or {}).get("inputs") or []
            radio_like = sum(1 for it in inputs if str(it.get("type") or "").lower() in ("radio", "checkbox"))
            if radio_like >= 1:
                looks_like_quiz = True
            if request.full_html and isinstance(request.full_html, str) and re.search(r"\bquiz\b|question\b|choices\b", request.full_html, flags=re.IGNORECASE):
                looks_like_quiz = True

            if looks_like_quiz:
                quiz_attempted = True
                quiz_data = {}
                if request.full_html:
                    quiz_data = _llm_extract_quiz_from_html(request.full_html, memory_context=memory_ctx) or {}
                if not quiz_data and inputs:
                    groups = {}
                    for inp in inputs:
                        name = inp.get("name") or inp.get("id") or "group"
                        groups.setdefault(name, []).append({
                            "text": inp.get("placeholder") or inp.get("label") or inp.get("name") or inp.get("id"),
                            "input_id": inp.get("id"),
                            "input_name": inp.get("name"),
                            "selector": inp.get("id") or inp.get("name"),
                        })
                    questions = []
                    for k, opts in groups.items():
                        questions.append({"question_text": k, "options": opts})
                    quiz_data = {"question_count": len(questions), "questions": questions, "submit_candidates": []}

                if quiz_data and quiz_data.get("question_count", 0) > 0:
                    qs_req = QuizSolveRequest(url=request.url, title=None, full_text=None, analysis_summary=None, quiz_data=quiz_data, full_html=request.full_html)
                    llm_answers = _llm_quiz_answers(qs_req, memory_context=memory_ctx)
                    if llm_answers:
                        verified_answers = _llm_verify_quiz_answers_against_html(
                            qs_req,
                            llm_answers,
                            memory_context=memory_ctx,
                        )
                        answers_out, actions = _answers_to_actions(quiz_data, verified_answers)
                    else:
                        actions = []
                    quiz_actions_count = len(actions)
    except Exception:
        pass

    # Write a compact automation debug entry
    try:
        entry = {
            "ts": int(time.time()),
            "query": request.query,
            "url": request.url,
            "dom_inputs": len((request.dom_map or {}).get("inputs") or []),
            "llm_called": llm_called,
            "llm_returned_actions": len(llm_actions or []),
            "final_actions_count": len(actions or []),
            "quiz_attempted": quiz_attempted,
            "quiz_actions_count": quiz_actions_count,
            "full_html_preview": _clean_html_preview(request.full_html or "")[:2000],
            "actions_preview": [
                {"type": a.type, "target": a.target, "value": a.value} for a in (actions or [])[:8]
            ],
            "memory": {
                "found_previous": memory_ctx.get("found_previous"),
                "content_changed": memory_ctx.get("content_changed"),
                "saved": memory_write.get("saved"),
                "url_hash": memory_write.get("url_hash"),
                "content_hash": memory_write.get("content_hash"),
            },
        }
        _write_automation_log(entry)
    except Exception:
        pass

    return AutomationPlanResponse(actions=actions)


@router.post("/quiz_solve", response_model=QuizSolveResponse)
def quiz_solve(request: QuizSolveRequest) -> QuizSolveResponse:
    current_scraped = {
        "url": request.url,
        "title": request.title,
        "full_text": request.full_text,
        "full_html": request.full_html,
        "quiz_data": request.quiz_data or {},
    }
    memory_ctx = _memory.memory_context(request.url, current_scraped)
    if request.url:
        _memory.remember_scrape(request.url, current_scraped)

    # If the extension did not provide quiz structure, attempt to extract it from full HTML via LLM
    if (not request.quiz_data or (isinstance(request.quiz_data, dict) and request.quiz_data.get("question_count", 0) == 0)) and request.full_html:
        try:
            extracted = _llm_extract_quiz_from_html(request.full_html, memory_context=memory_ctx)
            if extracted and extracted.get("question_count"):
                request.quiz_data = extracted
        except Exception:
            # proceed with whatever quiz_data is available
            pass

    # Strict LLM-only quiz solving path.
    llm_answers = _llm_quiz_answers(request, memory_context=memory_ctx)
    if llm_answers:
        verified_answers = _llm_verify_quiz_answers_against_html(
            request,
            llm_answers,
            memory_context=memory_ctx,
        )
        answers, actions = _answers_to_actions(request.quiz_data or {}, verified_answers)
    else:
        answers, actions = [], []
    return QuizSolveResponse(answers=answers, actions=actions)


@router.post("/agent_loop_tick", response_model=AgentLoopTickResponse)
def agent_loop_tick(request: AgentLoopTickRequest) -> AgentLoopTickResponse:
    events = request.events or []
    dom_map = request.dom_map or {}
    serialized_events = [e.model_dump() if hasattr(e, "model_dump") else e.dict() for e in events[-10:]]

    event_query = _loop_event_query(events)
    memory_ctx = _memory.memory_context(
        request.url,
        {
            "url": request.url,
            "title": request.title,
            "events": serialized_events,
            "dom_map": dom_map,
            "user_memory": request.user_memory,
        },
    )

    # Use LLM planner first for generality, with event stream encoded as query.
    llm_actions = _llm_automation_plan(
        query=f"Continuous loop tick: {event_query}",
        url=request.url,
        dom_map=dom_map,
        memory_context={
            "scrape_memory": memory_ctx,
            "user_memory": request.user_memory,
            "mode": "continuous_agent_loop",
        },
    )
    if llm_actions:
        return AgentLoopTickResponse(actions=llm_actions[:5], reason="LLM planner generated autonomous actions")

    fallback_actions, fallback_reason = _loop_fallback_actions(request)
    return AgentLoopTickResponse(actions=fallback_actions, reason=fallback_reason)
