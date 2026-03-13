# 🚀 QUICK START: Running Your API

## 1️⃣ Start the API Server

```bash
cd c:\Users\jaypa\OneDrive\Desktop\MEGAHACK-2026_Merge-ConflictX

# Start the API (with auto-reload for development)
python -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:

```
Uvicorn running on http://0.0.0.0:8000
```

✅ API is live at: **http://localhost:8000**

---

## 2️⃣ View API Documentation

Open your browser to:

- **Interactive API Explorer**: http://localhost:8000/docs
- **Alternative Swagger UI**: http://localhost:8000/redoc

You can test all endpoints directly in the browser!

---

## 3️⃣ Test Complete Workflow

In a new terminal window:

```bash
cd c:\Users\jaypa\OneDrive\Desktop\MEGAHACK-2026_Merge-ConflictX
python test_api.py
```

This will:

1. Upload a test document
2. Start an analysis job
3. Stream real-time progress
4. Fetch all panel data
5. Download a report

---

## 4️⃣ What Your Frontend Needs

### Upload & Run

```javascript
// Upload file
const formData = new FormData();
formData.append("file", fileInput.files[0]);
const upload = await fetch("http://localhost:8000/upload", {
  method: "POST",
  body: formData,
});
const { file_id } = await upload.json();

// Or run with text
const run = await fetch("http://localhost:8000/run", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ file_id }), // or { text: "..." }
});
const { job_id } = await run.json();
```

### Stream Real-time Events

```javascript
const eventSource = new EventSource(
  `http://localhost:8000/jobs/${job_id}/stream`,
);

eventSource.addEventListener("step_progress", (event) => {
  const { step_id, progress_pct, sub_tasks, metrics } = JSON.parse(event.data);
  // Update progress bar, sub-task list, metrics display
});

eventSource.addEventListener("step_complete", (event) => {
  const { step_id, verdict } = JSON.parse(event.data);
  // Show verdict card with flash, badge, title, risk, etc.
});

eventSource.addEventListener("pipeline_done", (event) => {
  const { confidence, runtime_seconds } = JSON.parse(event.data);
  // Mark job as complete, enable download button
});

eventSource.addEventListener("error", (event) => {
  const { message } = JSON.parse(event.data);
  // Show error message
});
```

### Fetch Panel Data

```javascript
// After streaming completes (or in parallel)
const stats = await fetch(`http://localhost:8000/jobs/${job_id}/stats`).then(
  (r) => r.json(),
);
const structure = await fetch(
  `http://localhost:8000/jobs/${job_id}/structure`,
).then((r) => r.json());
const radio = await fetch(`http://localhost:8000/jobs/${job_id}/radio`).then(
  (r) => r.json(),
);
const topics = await fetch(`http://localhost:8000/jobs/${job_id}/topics`).then(
  (r) => r.json(),
);
const clauses = await fetch(
  `http://localhost:8000/jobs/${job_id}/clauses`,
).then((r) => r.json());
const recommendations = await fetch(
  `http://localhost:8000/jobs/${job_id}/recommendations`,
).then((r) => r.json());
const insights = await fetch(
  `http://localhost:8000/jobs/${job_id}/insights`,
).then((r) => r.json());
const stakeholders = await fetch(
  `http://localhost:8000/jobs/${job_id}/stakeholders`,
).then((r) => r.json());
const risk = await fetch(`http://localhost:8000/jobs/${job_id}/risk`).then(
  (r) => r.json(),
);
```

### Download Report

```javascript
const report = await fetch(
  `http://localhost:8000/jobs/${job_id}/report?format=json`,
).then((r) => r.json());

// For PDF (when implemented):
// window.location = `http://localhost:8000/jobs/${job_id}/report?format=pdf`;
```

### Check Status & Abort

```javascript
// Get job status
const status = await fetch(`http://localhost:8000/jobs/${job_id}`).then((r) =>
  r.json(),
);
// { job_id, status: "queued|running|done|failed", current_step, elapsed_seconds, ... }

// Abort job
await fetch(`http://localhost:8000/jobs/${job_id}`, { method: "DELETE" });
```

### System Health

```javascript
const health = await fetch("http://localhost:8000/health").then((r) =>
  r.json(),
);
// { status: "ok", uptime_pct: 99.8, system_temp: "45.2°C" }
```

---

## 5️⃣ API Endpoints Summary

| Method | Path                                     | Purpose                                     |
| ------ | ---------------------------------------- | ------------------------------------------- |
| POST   | `/upload`                                | Upload file → get file_id                   |
| POST   | `/run`                                   | Start job with text or file_id → get job_id |
| GET    | `/jobs/{job_id}/stream`                  | SSE stream for real-time progress           |
| GET    | `/jobs/{job_id}`                         | Get job status                              |
| DELETE | `/jobs/{job_id}`                         | Abort job                                   |
| GET    | `/jobs/{job_id}/stats`                   | Pit stop stats + velocity sparkline         |
| GET    | `/jobs/{job_id}/structure`               | Document structure (aero analysis)          |
| GET    | `/jobs/{job_id}/radio`                   | Radio communications log                    |
| GET    | `/jobs/{job_id}/topics`                  | Topic distribution bars                     |
| GET    | `/jobs/{job_id}/clauses`                 | Detected clauses                            |
| GET    | `/jobs/{job_id}/recommendations`         | Strategic recommendations                   |
| GET    | `/jobs/{job_id}/insights`                | Analysis insights                           |
| GET    | `/jobs/{job_id}/stakeholders`            | Stakeholder impact ranking                  |
| GET    | `/jobs/{job_id}/risk`                    | Risk metrics and sentiment                  |
| GET    | `/jobs/{job_id}/report?format=json\|pdf` | Download report                             |
| GET    | `/health`                                | System health and uptime                    |

---

## 6️⃣ Testing with curl

### Upload

```bash
curl -X POST -F "file=@document.pdf" http://localhost:8000/upload
```

### Run Job

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"text":"Your document text here..."}' \
  http://localhost:8000/run
```

### Stream Events

```bash
curl http://localhost:8000/jobs/{JOB_ID}/stream
```

### Check Status

```bash
curl http://localhost:8000/jobs/{JOB_ID}
```

### Fetch Data

```bash
curl http://localhost:8000/jobs/{JOB_ID}/stats
curl http://localhost:8000/jobs/{JOB_ID}/structure
curl http://localhost:8000/jobs/{JOB_ID}/topics
# ... etc
```

### Download Report

```bash
curl http://localhost:8000/jobs/{JOB_ID}/report?format=json | jq .
```

### Abort Job

```bash
curl -X DELETE http://localhost:8000/jobs/{JOB_ID}
```

---

## 7️⃣ Current Implementation Status

✅ **Fully Implemented:**

- Job upload and kickoff
- SSE streaming with simulated pipeline
- All 9 panel data endpoints (with mock data)
- Job status and abort
- JSON report generation
- System health monitoring
- CORS for frontend integration
- Complete documentation

⏳ **Ready for Real Backend Integration:**

- Replace simulated pipeline in `routes/stream.py` with FinalPipeline
- Call actual analysis services in `routes/data.py`
- Implement PDF report generation in `routes/report.py`

---

## 8️⃣ File Structure

```
backend/
  api/
    models.py           ← Pydantic models & response types
    job_manager.py      ← Job state management
    main.py             ← FastAPI app setup & routes
    routes/
      upload.py         ← POST /upload, POST /run
      jobs.py           ← GET /jobs/{id}, DELETE /jobs/{id}
      data.py           ← All 9 panel data endpoints
      stream.py         ← GET /jobs/{id}/stream (SSE)
      report.py         ← GET /jobs/{id}/report
      analysis.py       ← (existing) analysis endpoints
      ingestion.py      ← (existing) ingestion endpoints
```

---

## 9️⃣ Next Steps

1. **Test the API**: Run `python test_api.py` ✅
2. **View Docs**: Open http://localhost:8000/docs ✅
3. **Integrate Frontend**: Use the code snippets above ✅
4. **Connect Real Pipeline**: Replace mocks with actual services
5. **Deploy**: Use Docker or cloud deployment (Azure, etc.)

---

## 🔗 See Also

- [Full API Documentation](API_DOCUMENTATION.md)
- [Backend Implementation Guide](BACKEND_IMPLEMENTATION.md)
- [Test Script](test_api.py)

---

**Everything is ready!** Just start the server and connect your frontend. 🎉
