from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path

from backend.app.services.scrape_memory_service import ScrapeMemoryService
from backend.app.services.ollama_service import OllamaService

router = APIRouter(tags=["mapping"])

STORAGE_DIR = Path(__file__).resolve().parents[3] / "mapping_store"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class NavigationStep(BaseModel):
    url: str
    title: Optional[str] = None
    selector: Optional[str] = None
    action: Optional[str] = None  # e.g., CLICK, INPUT, NAVIGATE
    value: Optional[str] = None
    timestamp: Optional[float] = None


class MappingUploadRequest(BaseModel):
    session_id: Optional[str] = Field(default_factory=lambda: uuid4().hex)
    steps: List[NavigationStep]
    metadata: Optional[Dict[str, Any]] = None


class MappingInfo(BaseModel):
    map_id: str
    session_id: str
    nodes: int
    edges: int
    saved_path: str


@router.post("/mapping/upload", response_model=MappingInfo)
def upload_navigation_trace(payload: MappingUploadRequest) -> MappingInfo:
    # basic validation
    if not payload.steps or len(payload.steps) < 1:
        raise HTTPException(status_code=400, detail="Payload must include at least one navigation step")

    map_id = f"map-{uuid4().hex[:12]}"
    filename = STORAGE_DIR / f"{map_id}.json"

    # Ensure we have a usable session_id even if client sent null
    session_id_val = payload.session_id or uuid4().hex

    # naive graph metrics: unique URLs as nodes, sequential transitions as edges
    urls = [s.url for s in payload.steps if s.url]
    unique_urls = list(dict.fromkeys(urls))
    edges = 0
    if len(urls) > 1:
        edges = len(urls) - 1

    store = {
        "map_id": map_id,
        "session_id": session_id_val,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "metadata": payload.metadata or {},
        "steps": [s.dict() for s in payload.steps],
    }

    try:
        with open(filename, "w", encoding="utf-8") as fh:
            json.dump(store, fh, ensure_ascii=False, indent=2)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist map: {exc}")

    return MappingInfo(
        map_id=map_id,
        session_id=session_id_val,
        nodes=len(unique_urls),
        edges=edges,
        saved_path=str(filename),
    )


@router.get("/mapping/item/{map_id}")
def get_mapping(map_id: str) -> Dict[str, Any]:
    filename = STORAGE_DIR / f"{map_id}.json"
    if not filename.exists():
        raise HTTPException(status_code=404, detail="Map not found")

    try:
        with open(filename, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read map: {exc}")


def _build_graph_from_steps(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Nodes keyed by URL
    nodes_map: Dict[str, Dict[str, Any]] = {}
    edges_map: Dict[str, Dict[str, Any]] = {}

    def node_id_for(url: str) -> str:
        return url

    # populate nodes with titles if available
    for s in steps:
        url = s.get("url") or ""
        if not url:
            continue
        if url not in nodes_map:
            nodes_map[url] = {"id": node_id_for(url), "url": url, "title": s.get("title") or ""}

    # build sequential edges
    for i in range(len(steps) - 1):
        a = steps[i]
        b = steps[i + 1]
        from_url = a.get("url") or ""
        to_url = b.get("url") or ""
        if not from_url or not to_url:
            continue

        key = f"{from_url}|||{to_url}|||{str(a.get('selector') or '')}|||{str(a.get('action') or '')}"
        if key not in edges_map:
            edges_map[key] = {
                "from": from_url,
                "to": to_url,
                "action": a.get("action") or None,
                "selector": a.get("selector") or None,
                "count": 0,
                "examples": []
            }
        edges_map[key]["count"] += 1
        if len(edges_map[key]["examples"]) < 4:
            edges_map[key]["examples"].append({"step_index": i, "step": a})

    # convert maps to lists
    nodes = list(nodes_map.values())
    edges = [v for v in edges_map.values()]
    return {"nodes": nodes, "edges": edges}


@router.get("/mapping/{map_id}/graph")
def get_mapping_graph(map_id: str) -> Dict[str, Any]:
    filename = STORAGE_DIR / f"{map_id}.json"
    if not filename.exists():
        raise HTTPException(status_code=404, detail="Map not found")
    try:
        with open(filename, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            steps = data.get("steps") or []
            graph = _build_graph_from_steps(steps)
            return {"map_id": map_id, "graph": graph, "meta": {"steps": len(steps)}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build graph: {exc}")

@router.get("/mapping/list")
def list_maps() -> Dict[str, Any]:
    files = []
    try:
        for p in STORAGE_DIR.glob("map-*.json"):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    files.append({
                        "map_id": data.get("map_id") or p.stem,
                        "session_id": data.get("session_id"),
                        "created_at": data.get("created_at"),
                        "steps": len(data.get("steps") or []),
                        "path": str(p)
                    })
            except Exception:
                continue
        # sort by created_at desc if present
        files.sort(key=lambda f: f.get("created_at") or "", reverse=True)
        return {"maps": files}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list maps: {exc}")


class PlanRequest(BaseModel):
    start_url: Optional[str] = None
    goal_url: str


@router.post("/mapping/{map_id}/plan")
def plan_path(map_id: str, req: PlanRequest) -> Dict[str, Any]:
    filename = STORAGE_DIR / f"{map_id}.json"
    if not filename.exists():
        raise HTTPException(status_code=404, detail="Map not found")
    try:
        with open(filename, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            steps = data.get("steps") or []
            graph = _build_graph_from_steps(steps)

            # Build adjacency by URL
            adj = {}
            for e in graph["edges"]:
                adj.setdefault(e["from"], []).append(e)

            start = req.start_url or (steps[0].get("url") if steps else None)
            if not start:
                raise HTTPException(status_code=400, detail="No start_url provided and map has no steps")

            # BFS to find path of URLs
            from collections import deque

            q = deque()
            q.append((start, [start]))
            visited = set([start])
            found_path = None
            while q:
                cur, path = q.popleft()
                if cur == req.goal_url:
                    found_path = path
                    break
                for edge in adj.get(cur, []):
                    nxt = edge.get("to")
                    if not nxt or nxt in visited:
                        continue
                    visited.add(nxt)
                    q.append((nxt, path + [nxt]))

            if not found_path:
                return {"ok": False, "message": "No path found between start and goal in this map."}

            # Convert URL path to action plan: for each transition, pick representative selector/action if available
            actions = []
            for i in range(len(found_path) - 1):
                fr = found_path[i]
                to = found_path[i + 1]
                # pick first matching edge
                candidates = [e for e in graph["edges"] if e["from"] == fr and e["to"] == to]
                edge = candidates[0] if candidates else None
                if edge and edge.get("selector"):
                    actions.append({"type": edge.get("action") or "CLICK", "target": edge.get("selector"), "delayMs": 400})
                else:
                    # fallback: navigate directly
                    actions.append({"type": "NAVIGATE", "url": to, "delayMs": 300})

            return {"ok": True, "path": found_path, "actions": actions}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute plan: {exc}")


class PlanGoalRequest(BaseModel):
    goal: str
    start_url: Optional[str] = None


@router.post("/mapping/{map_id}/plan_goal")
def plan_goal(map_id: str, req: PlanGoalRequest) -> Dict[str, Any]:
    """Generate an action plan to achieve a natural-language goal using the stored map
    and (when available) cached scraped HTML for pages. Falls back to URL-path planner
    if LLM planning fails."""
    filename = STORAGE_DIR / f"{map_id}.json"
    if not filename.exists():
        raise HTTPException(status_code=404, detail="Map not found")

    project_root = Path(__file__).resolve().parents[3]
    memory = ScrapeMemoryService(project_root=project_root)
    ollama = OllamaService()

    try:
        with open(filename, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            steps = data.get("steps") or []
            graph = _build_graph_from_steps(steps)

            start = req.start_url or (steps[0].get("url") if steps else None)
            if not start:
                raise HTTPException(status_code=400, detail="No start_url provided and map has no steps")

            # Gather a small set of representative nodes and scraped HTML when available
            node_samples = []
            for n in graph.get("nodes", [])[:12]:
                url = n.get("url")
                scraped = memory.load(url) or {}
                scraped_html = None
                try:
                    scraped_html = (scraped.get("latest") or {}).get("scraped") or {}
                except Exception:
                    scraped_html = None
                node_samples.append({"url": url, "title": n.get("title"), "scraped": scraped_html})

            system_prompt = (
                "You are an autonomous web navigation planner. Given a starting URL, a natural-language goal, "
                "a small graph of known pages (urls + titles), and optional scraped page contents, produce a JSON array 'actions' "
                "that, when executed by a browser automation layer, will achieve the goal. Use action types: CLICK, TYPE, SELECT, NAVIGATE, SCROLL. "
                "Prefer clicking visible buttons/selectors and filling inputs when required. Keep actions minimal and include delayMs for each action. "
                "Return JSON only with keys: {\"ok\": true|false, \"actions\": [ ... ], \"explanation\": string}"
            )

            user_obj = {
                "start_url": start,
                "goal": req.goal,
                "graph_nodes": [{"url": n.get("url"), "title": n.get("title")} for n in graph.get("nodes", [])[:20]],
                "node_samples": node_samples,
                "notes": "If a node's scraped content is provided, use it to find selectors/text to click. If not available, prefer NAVIGATE to the URL."
            }

            user_prompt = json.dumps(user_obj, ensure_ascii=False)
            plan = ollama.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)

            if isinstance(plan, dict) and plan.get("ok") and isinstance(plan.get("actions"), list):
                # Validate actions against scraped memory when possible
                validated = []
                for a in plan.get("actions", []):
                    a_copy = dict(a)
                    a_copy["valid"] = False
                    a_copy["matched_url"] = None
                    target = a_copy.get("target") or ""
                    url_target = a_copy.get("url") or ""

                    # If action targets a selector-like string, try to find it in sampled scraped HTML
                    if target:
                        for node in node_samples:
                            scraped = (node.get("scraped") or {})
                            full_html = ""
                            if isinstance(scraped, dict):
                                full_html = (scraped.get("full_html") or scraped.get("full_text") or "")
                            elif isinstance(scraped, str):
                                full_html = scraped
                            if full_html and target and target in full_html:
                                a_copy["valid"] = True
                                a_copy["matched_url"] = node.get("url")
                                break

                    # If action is a NAVIGATE, verify the target URL exists in memory
                    if not a_copy["valid"] and url_target:
                        mem = memory.load(url_target)
                        if mem:
                            a_copy["valid"] = True
                            a_copy["matched_url"] = url_target

                    validated.append(a_copy)

                return {"ok": True, "actions": validated, "explanation": plan.get("explanation")}

            # Fallback #1: try to interpret goal as a target URL/title substring and use path planner
            goal_lower = req.goal.lower()
            candidate = None
            for n in graph.get("nodes", []):
                if goal_lower in (n.get("title") or "").lower() or goal_lower in (n.get("url") or "").lower():
                    candidate = n.get("url")
                    break

            if candidate:
                plan_req = PlanRequest(start_url=start, goal_url=candidate)
                return plan_path(map_id, plan_req)

            # Fallback #2: keyword/synonym heuristic (checks URL, title, and scraped content)
            # Useful for goals like "forgot password" where titles may be localized or terse.
            heuristics = set()
            # base tokens from the goal
            for t in re.findall(r"\w+", goal_lower):
                heuristics.add(t)
            # common synonyms for password-related flows
            if "password" in goal_lower or "forgot" in goal_lower or "reset" in goal_lower:
                heuristics.update(["forgot", "reset", "password", "resetpassword", "forgotpassword", "change-password", "forgot-password"])

            candidate2 = None
            for n in graph.get("nodes", []):
                title = (n.get("title") or "").lower()
                url = (n.get("url") or "").lower()
                scraped_text = ""
                try:
                    mem = memory.load(n.get("url") or "") or {}
                    scraped = (mem.get("latest") or {}).get("scraped") or {}
                    if isinstance(scraped, dict):
                        scraped_text = (scraped.get("full_text") or scraped.get("full_html") or "")
                    elif isinstance(scraped, str):
                        scraped_text = scraped
                except Exception:
                    scraped_text = ""

                hay = " ".join([title, url, (scraped_text or "").lower()])
                for token in heuristics:
                    if token and token in hay:
                        candidate2 = n.get("url")
                        break
                if candidate2:
                    break

            if candidate2:
                plan_req = PlanRequest(start_url=start, goal_url=candidate2)
                return plan_path(map_id, plan_req)

            # Fuzzy heuristic: try token overlap between goal and node titles/urls/scraped content
            goal_tokens = set(re.findall(r"\w+", goal_lower))
            best = None
            best_score = 0
            for n in graph.get("nodes", []):
                score = 0
                title = (n.get("title") or "").lower()
                url = (n.get("url") or "").lower()
                scraped_text = ""
                try:
                    mem = memory.load(n.get("url") or "") or {}
                    scraped = (mem.get("latest") or {}).get("scraped") or {}
                    if isinstance(scraped, dict):
                        scraped_text = (scraped.get("full_text") or scraped.get("full_html") or "")
                    elif isinstance(scraped, str):
                        scraped_text = scraped
                except Exception:
                    scraped_text = ""

                hay = " ".join([title, url, (scraped_text or "").lower()])
                for t in goal_tokens:
                    if t and t in hay:
                        score += 1

                if score > best_score:
                    best_score = score
                    best = n.get("url")

            if best_score > 0 and best:
                plan_req = PlanRequest(start_url=start, goal_url=best)
                return plan_path(map_id, plan_req)

            return {"ok": False, "message": "LLM planning failed and no candidate page matched the goal."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate plan for goal: {exc}")
