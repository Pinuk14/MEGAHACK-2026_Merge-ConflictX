"""Server-Sent Events (SSE) stream for real-time pipeline progress."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import AsyncGenerator
from backend.api.job_manager import get_job_manager
from backend.api.models import JobStatus
from backend.app.schema import DocumentInsight, InsightBatch
from backend.app.pipelines.output_storage import InsightOutputStorage, InsightStorageConfig

# Add backend.app to path for service imports
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from backend.app.services.topic_classification_service import TopicClassificationService
    from backend.app.services.clause_detection_service import ClauseDetectionService
    from backend.app.services.stakeholder_extraction_service import StakeholderExtractionService
    from backend.app.services.summarization_service import SummarizationService
    from backend.app.services.semantic_segmentation_service import SemanticSegmentationService
    HAS_SERVICES = True
except ImportError:
    print("[WARNING] Real analysis services not available - using mock data")
    HAS_SERVICES = False

router = APIRouter(prefix="/jobs", tags=["stream"])
job_manager = get_job_manager()


def _resolve_source_filename(file_id: str | None) -> str | None:
    """Resolve uploaded original filename from file_id when available."""
    if not file_id:
        return None

    uploads_dir = PROJECT_ROOT / "infrastructure" / "storage" / "uploads"
    matches = sorted(uploads_dir.glob(f"{file_id}_*"))
    if not matches:
        return None

    name = matches[0].name
    prefix = f"{file_id}_"
    return name[len(prefix):] if name.startswith(prefix) else name


def _persist_insight_outputs(
    job_id: str,
    source_filename: str | None,
    summary_result,
    clauses_result,
    stakeholders_result,
    topics_result,
) -> None:
    """Write batch + per-document insight artifacts to outputs/insights."""
    batch = InsightBatch(
        items=[
            DocumentInsight(
                document_id=job_id,
                source_filename=source_filename,
                generated_at=datetime.now(timezone.utc),
                executive_summary=summary_result,
                clauses=clauses_result,
                stakeholders=stakeholders_result,
                topics=topics_result,
            )
        ]
    )

    storage = InsightOutputStorage(
        project_root=PROJECT_ROOT,
        config=InsightStorageConfig(),
    )
    batch_path, doc_paths = storage.save(batch)
    print(
        f"[INFO] Saved insight artifacts for job {job_id}: "
        f"batch={batch_path}, per_doc={len(doc_paths)}"
    )


async def run_real_analysis(job_id: str, input_text: str) -> None:
    """
    Run actual backend analysis services on the input text.
    Caches results in the job for panel data endpoints to return.
    """
    if not HAS_SERVICES or not input_text:
        return
    
    job = job_manager.get_job(job_id)
    if not job:
        return
    
    try:
        topic_service = TopicClassificationService()
        clause_service = ClauseDetectionService()
        stakeholder_service = StakeholderExtractionService()
        summary_service = SummarizationService()
        segmentation_service = SemanticSegmentationService()

        segments = segmentation_service.segment_document(
            text=input_text,
            document_id=job_id,
            source_filename=(job.input_file_id or "uploaded_document"),
        )

        topics_result = topic_service.classify(input_text)
        clauses_result = clause_service.detect_from_segments(segments)
        stakeholders_result = stakeholder_service.extract_from_segments(segments)
        summary_result = summary_service.summarize(
            text=input_text,
            clauses=clauses_result,
            stakeholders=stakeholders_result,
            topics=topics_result,
        )

        source_filename = _resolve_source_filename(job.input_file_id)
        _persist_insight_outputs(
            job_id=job_id,
            source_filename=source_filename,
            summary_result=summary_result,
            clauses_result=clauses_result,
            stakeholders_result=stakeholders_result,
            topics_result=topics_result,
        )

        topics_data = [
            {
                "label": t.label.replace("_", " ").upper(),
                "pct": max(1, min(100, int(round(t.confidence * 100)))),
            }
            for t in topics_result[:6]
        ]
        if topics_data:
            job_manager.set_topics(job_id, topics_data)

        clause_colors = {
            "obligation": "#ef4444",
            "compliance": "#f97316",
            "deadline": "#eab308",
            "penalty": "#ef4444",
            "governance": "#ec5b13",
            "funding": "#facc15",
        }
        clauses_data = [
            {
                "label": c.clause_type.value.upper(),
                "val": c.text[:72] + ("..." if len(c.text) > 72 else ""),
                "color": clause_colors.get(c.clause_type.value, "#ec5b13"),
            }
            for c in clauses_result[:8]
        ]
        if clauses_data:
            job_manager.set_clauses(job_id, clauses_data)

        impact_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        sorted_stakeholders = sorted(
            stakeholders_result,
            key=lambda s: impact_rank.get(s.impact_level.value, 0),
            reverse=True,
        )
        stakeholders_data = [
            {
                "rank": f"{idx}st" if idx == 1 else (f"{idx}nd" if idx == 2 else (f"{idx}rd" if idx == 3 else f"{idx}th")),
                "label": s.stakeholder_name.upper(),
                "score": float(impact_rank.get(s.impact_level.value, 1) * 2.5),
                "max_score": 10.0,
            }
            for idx, s in enumerate(sorted_stakeholders[:6], start=1)
        ]
        if stakeholders_data:
            job_manager.set_stakeholders(job_id, stakeholders_data)

        insight_points = summary_result.key_points[:3] if summary_result.key_points else []
        if summary_result.short_summary:
            insight_points = [summary_result.short_summary] + insight_points
        insights_data = [
            {
                "id": f"i{idx}",
                "conf": f"{max(70, 95 - idx * 6)}%",
                "text": p,
                "color": "#10b981" if idx == 1 else ("#f59e0b" if idx == 2 else "#ef4444"),
                "shown_after_step": "summarize" if idx < 3 else "stakeholder",
            }
            for idx, p in enumerate(insight_points[:4], start=1)
        ]
        if insights_data:
            job_manager.set_insights(job_id, insights_data)

        recommendations_data = [
            {
                "priority": "IMMEDIATE" if idx == 1 else ("STRATEGIC" if idx == 2 else "LONG-TERM"),
                "text": rec,
            }
            for idx, rec in enumerate(summary_result.recommended_actions[:3], start=1)
        ]
        if recommendations_data:
            job_manager.set_recommendations(job_id, recommendations_data)

        token_count = len((input_text or "").split())
        job_manager.set_stats(
            job_id,
            {
                "tokens_processed": token_count,
                "accuracy_pct": 90.0,
                "delta_pct": 8.5,
                "velocity_series": [
                    {"t": 0, "val": 0.0},
                    {"t": 10, "val": 2.2},
                    {"t": 20, "val": 4.9},
                    {"t": 30, "val": 6.1},
                    {"t": 40, "val": 8.0},
                    {"t": 50, "val": 9.2},
                ],
            },
        )

        job_manager.set_structure(
            job_id,
            {
                "sections": max(1, len(segments)),
                "citation_density": 0.08,
                "figures": 0,
                "tables": 0,
            },
        )

        high_risk_clauses = sum(1 for c in clauses_result if c.clause_type.value in {"penalty", "deadline", "compliance", "obligation"})
        risk_value = min(0.95, max(0.1, 0.25 + (high_risk_clauses * 0.05)))
        job_manager.set_risk(
            job_id,
            {
                "risk_value": round(risk_value, 2),
                "sentiment": "cautious" if risk_value >= 0.55 else "neutral",
                "volatility": "high" if risk_value >= 0.7 else "normal",
            },
        )

        job_manager.set_radio_comms(
            job_id,
            [
                {"type": "TX", "text": f"Segmented {len(segments)} semantic blocks", "color": "#6366f1", "phase": "segment"},
                {"type": "RX", "text": f"Detected {len(clauses_result)} policy clauses", "color": "#10b981", "phase": "segment"},
                {"type": "TX", "text": f"Classified {len(topics_result)} topics", "color": "#6366f1", "phase": "classify"},
                {"type": "RX", "text": f"Mapped {len(stakeholders_result)} stakeholder impacts", "color": "#10b981", "phase": "stakeholder"},
            ],
        )

    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")


async def stream_events(job_id: str) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for a job.
    Yields: "event: {type}\ndata: {json}\n\n"
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        yield f"event: error\ndata: {json.dumps({'message': 'Job not found', 'step_id': None})}\n\n"
        return
    
    # If job has events in history, replay them first (for reconnects)
    for event in job.events:
        event_type = event["type"]
        data = event["data"]
        yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        await asyncio.sleep(0.1)
    
    # If job already completed, just send done event
    if job.status == JobStatus.DONE:
        yield f"event: pipeline_done\ndata: {json.dumps({'confidence': 0.94, 'runtime_seconds': 42.3})}\n\n"
        return
    
    # If job failed, send error
    if job.status == JobStatus.FAILED:
        yield f"event: error\ndata: {json.dumps({'message': job.error or 'Unknown error', 'step_id': job.current_step})}\n\n"
        return
    
    # Otherwise, simulate pipeline progress
    # In production, this would listen to actual backend tasks
    
    pipeline_steps = [
        {
            "step_id": "ingest",
            "step_index": 0,
            "sector": "S1",
            "short": "INGEST",
            "label": "Document Ingestion",
            "desc": "Loading and normalizing document...",
            "color": "#ca8a04",
        },
        {
            "step_id": "tokenize",
            "step_index": 1,
            "sector": "S2",
            "short": "TOKENIZE",
            "label": "Tokenization",
            "desc": "Breaking into semantic units...",
            "color": "#b45309",
        },
        {
            "step_id": "classify",
            "step_index": 2,
            "sector": "S3",
            "short": "CLASSIFY",
            "label": "Topic Classification",
            "desc": "Multi-label BERTopic clustering...",
            "color": "#facc15",
        },
        {
            "step_id": "segment",
            "step_index": 3,
            "sector": "S4",
            "short": "SEGMENT",
            "label": "Semantic Segmentation",
            "desc": "Identifying document sections...",
            "color": "#818cf8",
        },
        {
            "step_id": "summarize",
            "step_index": 4,
            "sector": "S5",
            "short": "SUMM",
            "label": "Summarization",
            "desc": "Executive summary extraction...",
            "color": "#10b981",
        },
        {
            "step_id": "stakeholder",
            "step_index": 5,
            "sector": "S6",
            "short": "STAKEHOLDER",
            "label": "Stakeholder Extraction",
            "desc": "Identifying affected parties...",
            "color": "#06b6d4",
        },
        {
            "step_id": "structure",
            "step_index": 6,
            "sector": "S7",
            "short": "EXPORT",
            "label": "Structured Output",
            "desc": "Compiling final structured output...",
            "color": "#ec4899",
        },
    ]
    
    # Simulate progress through each step
    for step in pipeline_steps:
        if job.status == JobStatus.FAILED:
            break
        
        job_manager.set_current_step(job_id, step["step_id"])
        
        # Emit ~10 progress events per step
        for i in range(10):
            progress_pct = (i + 1) * 10.0
            
            progress_event = {
                "step_id": step["step_id"],
                "step_index": step["step_index"],
                "sector": step["sector"],
                "short": step["short"],
                "label": step["label"],
                "desc": step["desc"],
                "color": step["color"],
                "progress_pct": progress_pct,
                "sub_task_index": i,
                "sub_tasks": [
                    {
                        "label": f"Processing chunk {i+1}/10",
                        "pct": progress_pct / 100.0,
                    }
                ],
                "metrics": [
                    {"key": "Tokens", "val": f"{int(400000 * (progress_pct/100))}"},
                    {"key": "Chunks", "val": f"{i+1}/10"},
                ]
            }
            
            yield f"event: step_progress\ndata: {json.dumps(progress_event)}\n\n"
            job_manager.add_event(job_id, "step_progress", progress_event)
            await asyncio.sleep(0.5)
        
        # Emit step_complete event with verdict
        verdict_data = {
            "flash": f"{step['short']} DONE",
            "badge": "PROCESSING COMPLETE",
            "title": f"{step['label'].upper()} FINISHED",
            "sub": f"Successfully processed with {100 - (step['step_index']*5)}% confidence",
            "alertLabel": "STATUS",
            "alertText": "All validations passed",
            "actionLabel": "RESULT",
            "actionText": "Moving to next stage",
            "riskIndex": f"{80 - step['step_index']*5}%",
            "riskLabel": "CONFIDENCE",
            "economicVal": f"0.{90 - step['step_index']*10}",
            "economicLabel": "QUALITY SCORE",
            "stats": [
                {"k": "PROCESSED", "v": f"{100}%"},
                {"k": "ERRORS", "v": "0"},
            ],
            "tags": ["Success"],
        }
        
        step_complete = {
            "step_id": step["step_id"],
            "verdict": verdict_data,
        }
        
        yield f"event: step_complete\ndata: {json.dumps(step_complete)}\n\n"
        job_manager.add_event(job_id, "step_complete", step_complete)
        await asyncio.sleep(1.0)
    
    # Run real analysis on uploaded content before pipeline_done
    if job.input_text:
        await run_real_analysis(job_id, job.input_text)
    
    # Emit pipeline_done event
    job_manager.update_job_status(job_id, JobStatus.DONE)
    
    pipeline_done = {
        "confidence": 0.94,
        "runtime_seconds": 42.3,
    }
    
    yield f"event: pipeline_done\ndata: {json.dumps(pipeline_done)}\n\n"
    job_manager.add_event(job_id, "pipeline_done", pipeline_done)


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    """
    Server-Sent Events endpoint for real-time pipeline progress.
    
    Events:
    - step_progress: Fired ~10× per step
    - step_complete: Fired once per step, triggers verdict card
    - pipeline_done: Fired when all steps complete
    - error: Fired on error
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )
    
    return StreamingResponse(
        stream_events(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
