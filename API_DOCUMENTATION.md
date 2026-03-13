"""
FastAPI Backend Documentation & Examples

This file contains examples of how to use the Merge-ConflictX Pipeline API.

## Quick Start

1. Run the API:

   ```
   uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Frontend will connect to: http://localhost:8000

## Complete API Workflow

### Step 1: Upload a file

POST /upload
Body: multipart/form-data with file

Response:
{
"file_id": "file_a1b2c3d4",
"filename": "document.pdf",
"size_bytes": 245000
}

### Step 2: Kickoff analysis job

POST /run
Body: {
"text": "Optional raw text",
"file_id": "file_a1b2c3d4" // or use text, not both required
}

Response:
{
"job_id": "550e8400-e29b-41d4-a716-446655440000",
"status": "queued"
}

### Step 3: Stream real-time progress (SSE)

GET /jobs/{job_id}/stream

The browser/client opens an EventSource connection to this endpoint.
Events emitted:

- step_progress (x10 per step)
- step_complete (x1 per step)
- pipeline_done (x1 at end)
- error (if failure)

### Step 4: Fetch panel data (while or after streaming)

The frontend polls these in parallel:

GET /jobs/{job_id}/stats
GET /jobs/{job_id}/structure
GET /jobs/{job_id}/radio
GET /jobs/{job_id}/topics
GET /jobs/{job_id}/clauses
GET /jobs/{job_id}/recommendations
GET /jobs/{job_id}/insights
GET /jobs/{job_id}/stakeholders
GET /jobs/{job_id}/risk
GET /jobs/{job_id} (status check)

### Step 5: Download report

GET /jobs/{job_id}/report?format=json
GET /jobs/{job_id}/report?format=pdf

### Step 6: Abort (optional)

DELETE /jobs/{job_id}

---

## Environment

The API needs these directories to exist:

- infrastructure/storage/uploads/ (file uploads)
- infrastructure/storage/outputs/ (reports)
- infrastructure/storage/raw_documents/ (text files)

---

## Frontend Integration Checklist

- [ ] Upload button -> POST /upload
- [ ] Green flag button (run) -> POST /run with text or file_id
- [ ] SSE EventSource to /jobs/{job_id}/stream for animated pipeline
- [ ] Display step_progress events in real-time
- [ ] Trigger verdict card on step_complete events
- [ ] Poll GET endpoints for panel data
- [ ] Show pipeline_done event as final state
- [ ] Download button -> GET /jobs/{job_id}/report?format=json
- [ ] System health in footer -> GET /health
- [ ] Abort button -> DELETE /jobs/{job_id}

---

## Testing with curl

# Upload file

curl -X POST -F "file=@document.pdf" http://localhost:8000/upload

# Kickoff job with text

curl -X POST -H "Content-Type: application/json" \\
-d '{"text":"Your document content here..."}' \\
http://localhost:8000/run

# Check job status

curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000

# Stream events (will show SSE stream)

curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/stream

# Get stats

curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/stats

# Download JSON report

curl http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000/report?format=json

# Abort job

curl -X DELETE http://localhost:8000/jobs/550e8400-e29b-41d4-a716-446655440000

---

## SSE Event Examples

### step_progress event

{
"step_id": "classify",
"step_index": 2,
"sector": "S2",
"short": "CLASSIFY",
"label": "Topic Classification",
"desc": "Multi-label BERTopic...",
"color": "#facc15",
"progress_pct": 47.2,
"sub_task_index": 2,
"sub_tasks": [{ "label": "Running BERTopic model", "pct": 0.26 }],
"metrics": [{ "key": "Domain", "val": "Healthcare" }]
}

### step_complete event

{
"step_id": "classify",
"verdict": {
"flash": "CLASSIFICATION DONE",
"badge": "ECONOMIC ADVANTAGE",
"title": "7 TOPIC CLUSTERS IDENTIFIED",
"sub": "...",
"alertLabel": "TOPIC DISTRIBUTION",
"alertText": "Regulatory Compliance 34%...",
"actionLabel": "DOMAIN CONFIRMED",
"actionText": "Primary domain: Healthcare...",
"riskIndex": "94%",
"riskLabel": "CONFIDENCE",
"economicVal": "0.87",
"economicLabel": "COHERENCE SCORE",
"stats": [{ "k": "TOPICS", "v": "7" }],
"tags": ["BERTopic 0.16"]
}
}

### pipeline_done event

{
"confidence": 0.94,
"runtime_seconds": 42.3
}

---

## Note for Future Development

The current implementation includes mock/default data for all endpoints.
To integrate with real backend services:

1. In job_manager.py, expand JobData to store results from actual services
2. In routes/stream.py, connect to real pipeline orchestration
3. In routes/data.py, populate caches from actual analysis results
4. Add task queuing (Celery/RQ) for background processing
5. Implement actual PDF report generation with reportlab or similar

The structure is designed to make this integration straightforward.

"""
