# API Complete Endpoint Reference

## 🎯 Endpoint Overview

### 1. File Upload

```
POST /upload
├─ Input: multipart/form-data with file
├─ Returns: { file_id, filename, size_bytes }
└─ Purpose: Store file for later processing
```

### 2. Job Kickoff

```
POST /run
├─ Input: { text?: string, file_id?: string }
├─ Returns: { job_id, status: "queued" }
└─ Purpose: Start analysis pipeline asynchronously
```

### 3. Real-time Progress Stream

```
GET /jobs/{job_id}/stream (Server-Sent Events)
├─ Event: step_progress (x10 per step)
│  └─ Data: {
│     ├─ step_id: "classify"
│     ├─ step_index: 2
│     ├─ sector: "S3"
│     ├─ short: "CLASSIFY"
│     ├─ label: "Topic Classification"
│     ├─ desc: "Multi-label BERTopic..."
│     ├─ color: "#facc15"
│     ├─ progress_pct: 47.2
│     ├─ sub_task_index: 2
│     ├─ sub_tasks: [{ label: "...", pct: 0.26 }]
│     └─ metrics: [{ key: "Domain", val: "Healthcare" }]
│
├─ Event: step_complete (x1 per step)
│  └─ Data: {
│     ├─ step_id: "classify"
│     └─ verdict: {
│        ├─ flash: "CLASSIFICATION DONE"
│        ├─ badge: "ECONOMIC ADVANTAGE"
│        ├─ title: "7 TOPIC CLUSTERS IDENTIFIED"
│        ├─ sub: "..."
│        ├─ alertLabel: "TOPIC DISTRIBUTION"
│        ├─ alertText: "Regulatory Compliance 34%..."
│        ├─ actionLabel: "DOMAIN CONFIRMED"
│        ├─ actionText: "Primary domain: Healthcare..."
│        ├─ riskIndex: "94%"
│        ├─ riskLabel: "CONFIDENCE"
│        ├─ economicVal: "0.87"
│        ├─ economicLabel: "COHERENCE SCORE"
│        ├─ stats: [{ k: "TOPICS", v: "7" }]
│        └─ tags: ["BERTopic 0.16"]
│
├─ Event: pipeline_done (x1 at end)
│  └─ Data: { confidence: 0.94, runtime_seconds: 42.3 }
│
└─ Event: error (if failure)
   └─ Data: { message: "...", step_id: "..." }
```

### 4. Job Status

```
GET /jobs/{job_id}
├─ Returns: {
│  ├─ job_id: "550e8400-..."
│  ├─ status: "queued|running|done|failed"
│  ├─ current_step: "classify"
│  ├─ elapsed_seconds: 42
│  ├─ created_at: "2026-03-13T10:30:00Z"
│  └─ completed_at: "2026-03-13T10:31:00Z" (if done)
└─ Purpose: Check job status for reconnects/polling
```

### 5. Pit Stop Stats

```
GET /jobs/{job_id}/stats
├─ Returns: {
│  ├─ tokens_processed: 4250000
│  ├─ accuracy_pct: 94.2
│  ├─ delta_pct: 12.3
│  └─ velocity_series: [
│     ├─ { t: 0, val: 0.0 }
│     ├─ { t: 10, val: 2.5 }
│     └─ ...
│  ]
└─ Purpose: Populate pit stop stats + velocity sparkline
```

### 6. Aero Analysis

```
GET /jobs/{job_id}/structure
├─ Returns: {
│  ├─ sections: 12
│  ├─ citation_density: 0.18
│  ├─ figures: 3
│  └─ tables: 5
└─ Purpose: Show document structure breakdown
```

### 7. Radio Communications

```
GET /jobs/{job_id}/radio
├─ Returns: {
│  └─ comms: [
│     ├─ { type: "TX", text: "Initiating...", color: "#...", phase: "ingest" }
│     ├─ { type: "RX", text: "256MB buffered", color: "#...", phase: "ingest" }
│     └─ ...
│  ]
└─ Purpose: Timeline of processing steps
```

### 8. Topic Distribution

```
GET /jobs/{job_id}/topics
├─ Returns: {
│  └─ topics: [
│     ├─ { label: "GOVERNANCE", pct: 88 }
│     ├─ { label: "LIABILITY", pct: 65 }
│     └─ { label: "SUSTAINABILITY", pct: 42 }
│  ]
└─ Purpose: Horizontal bar chart of topics
```

### 9. Scrutineering Clauses

```
GET /jobs/{job_id}/clauses
├─ Returns: {
│  └─ clauses: [
│     ├─ { label: "Indemnification", val: "Cross-party", color: "#ef4444" }
│     ├─ { label: "Warranty", val: "12-month", color: "#f97316" }
│     └─ ...
│  ]
└─ Purpose: Key clauses with colors
```

### 10. Race Strategy

```
GET /jobs/{job_id}/recommendations
├─ Returns: {
│  └─ recommendations: [
│     ├─ { priority: "IMMEDIATE", text: "Flag regulatory exposure..." }
│     ├─ { priority: "STRATEGIC", text: "Negotiate liability caps..." }
│     └─ { priority: "LONG-TERM", text: "Develop IP covenants..." }
│  ]
└─ Purpose: Three-column recommendation grid
```

### 11. Race Results

```
GET /jobs/{job_id}/insights
├─ Returns: {
│  └─ insights: [
│     ├─ { id: "i1", conf: "92%", text: "Healthcare dominates...", color: "#...", shown_after_step: "segment" }
│     ├─ { id: "i2", conf: "87%", text: "High regulatory...", color: "#...", shown_after_step: "summarize" }
│     └─ ...
│  ]
└─ Purpose: Key insights with fade-in timing
```

### 12. Constructors Standings

```
GET /jobs/{job_id}/stakeholders
├─ Returns: {
│  └─ groups: [
│     ├─ { rank: "1st", label: "Regulators", score: 95, max_score: 100 }
│     ├─ { rank: "2nd", label: "Customers", score: 78, max_score: 100 }
│     └─ ...
│  ]
└─ Purpose: Stakeholder impact ranking
```

### 13. Track Conditions

```
GET /jobs/{job_id}/risk
├─ Returns: {
│  ├─ risk_value: 0.72
│  ├─ sentiment: "cautious"
│  └─ volatility: "high"
└─ Purpose: Risk gauge circular SVG
```

### 14. Report Download

```
GET /jobs/{job_id}/report?format=json
├─ Returns: Complete JSON report with all analysis data
└─ Purpose: Download briefing document

GET /jobs/{job_id}/report?format=pdf
├─ Returns: PDF binary with Content-Disposition: attachment
└─ Purpose: Download formatted report
```

### 15. Job Abort

```
DELETE /jobs/{job_id}
├─ Returns: { status: "aborted", job_id: "..." }
└─ Purpose: Cancel running job
```

### 16. System Health

```
GET /health
├─ Returns: {
│  ├─ status: "ok"
│  ├─ uptime_pct: 99.8
│  └─ system_temp: "45.2°C"
└─ Purpose: Footer system status display
```

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
├─────────────────────────────────────────────────────────────────┤
│  [Upload]  [Run Job]  [Stream]  [Status]  [Panels]  [Download] │
└──────┬──────────┬─────────┬──────────┬─────────┬────────┬───────┘
       │          │         │          │         │        │
       v          v         v          v         v        v
    POST /     POST /    GET /jobs/   GET /    GET /*   GET /*
    upload      run      {id}/stream  {id}/    stats    report
       │          │         │          │       /radio
       │          │         │          │       /topics
       │          │         │          │       /clauses
       │          │         │          │       /insights
       │          │         │          │       /stakeholders
       │          │         │          │       /risk
       │          │         │          │         │
       └──────────┴─────────┴──────────┴─────────┴─────────┘
                           │
                           v
       ┌───────────────────────────────────────────────┐
       │           FastAPI Backend (main.py)           │
       ├───────────────────────────────────────────────┤
       │  routes/upload.py    (POST /, POST /run)      │
       │  routes/jobs.py      (GET /, DELETE /)        │
       │  routes/stream.py    (GET /stream)            │
       │  routes/data.py      (GET /*)                 │
       │  routes/report.py    (GET /report)            │
       └───────────────────────────────────────────────┘
                           │
                           v
       ┌───────────────────────────────────────────────┐
       │        JobManager (job_manager.py)            │
       ├───────────────────────────────────────────────┤
       │  Tracks:                                      │
       │  • Job status & metadata                      │
       │  • SSE event history                          │
       │  • Cached panel data                          │
       │  • Error state                                │
       └───────────────────────────────────────────────┘
                           │
                           v
       ┌───────────────────────────────────────────────┐
       │     Backend Pipelines (to be integrated)      │
       ├───────────────────────────────────────────────┤
       │  FinalPipeline (orchestration.py)             │
       │  Services (analysis, segmentation, etc.)      │
       │  Models (tfidf, embeddings, etc.)             │
       └───────────────────────────────────────────────┘
```

---

## 🔄 Request/Response Cycle Examples

### Example 1: Upload → Run → Stream

```
1. Upload File
   POST /upload
   ↓
   { file_id: "file_a1b2c3d4", filename: "doc.pdf", size_bytes: 245000 }

2. Kickoff Job
   POST /run
   body: { file_id: "file_a1b2c3d4" }
   ↓
   { job_id: "550e8400-...", status: "queued" }

3. Stream Progress
   GET /jobs/550e8400-.../stream
   ↓
   event: step_progress
   data: { step_id: "ingest", progress_pct: 10, ... }

   event: step_progress
   data: { step_id: "ingest", progress_pct: 20, ... }

   ... (x8 more step_progress events)

   event: step_complete
   data: { step_id: "ingest", verdict: { flash: "INGEST DONE", ... } }

   ... (repeat for 6 more steps)

   event: pipeline_done
   data: { confidence: 0.94, runtime_seconds: 42.3 }
```

### Example 2: Fetch Panel Data

```
After stream completes, fetch all panels in parallel:

GET /jobs/{job_id}/stats → { tokens_processed, accuracy_pct, velocity_series }
GET /jobs/{job_id}/structure → { sections, citation_density, figures, tables }
GET /jobs/{job_id}/radio → { comms: [...] }
GET /jobs/{job_id}/topics → { topics: [...] }
GET /jobs/{job_id}/clauses → { clauses: [...] }
GET /jobs/{job_id}/recommendations → { recommendations: [...] }
GET /jobs/{job_id}/insights → { insights: [...] }
GET /jobs/{job_id}/stakeholders → { groups: [...] }
GET /jobs/{job_id}/risk → { risk_value, sentiment, volatility }
```

### Example 3: Download Report

```
After analysis complete:

GET /jobs/{job_id}/report?format=json
↓
{ job_id: "...", created_at: "...", status: "done",
  summary: {...}, topics: [...], clauses: [...], ... }

Or:

GET /jobs/{job_id}/report?format=pdf
↓
[PDF binary content]
Content-Type: application/pdf
Content-Disposition: attachment; filename=report_550e8400....pdf
```

---

## 🎮 Frontend Integration Pseudo-code

```javascript
// 1. UPLOAD & RUN
async function analyzeDocument(fileOrText) {
  let jobId;

  if (typeof fileOrText === 'string') {
    // Direct text
    const res = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: fileOrText })
    });
    jobId = (await res.json()).job_id;
  } else {
    // File upload
    const formData = new FormData();
    formData.append('file', fileOrText);
    const uploadRes = await fetch('/upload', {
      method: 'POST',
      body: formData
    });
    const { file_id } = await uploadRes.json();

    const runRes = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_id })
    });
    jobId = (await runRes.json()).job_id;
  }

  // 2. STREAM PROGRESS
  const eventSource = new EventSource(`/jobs/${jobId}/stream`);

  eventSource.addEventListener('step_progress', (e) => {
    const { progress_pct, step_id } = JSON.parse(e.data);
    updateProgressBar(progress_pct);
    updateCurrentStep(step_id);
  });

  eventSource.addEventListener('step_complete', (e) => {
    const { verdict } = JSON.parse(e.data);
    showVerdictCard(verdict);
  });

  eventSource.addEventListener('pipeline_done', (e) => {
    const { confidence, runtime_seconds } = JSON.parse(e.data);
    eventSource.close();

    // 3. FETCH PANEL DATA
    const [stats, structure, radio, topics, clauses, recs, insights, stakeholders, risk] =
      await Promise.all([
        fetch(`/jobs/${jobId}/stats`).then(r => r.json()),
        fetch(`/jobs/${jobId}/structure`).then(r => r.json()),
        fetch(`/jobs/${jobId}/radio`).then(r => r.json()),
        fetch(`/jobs/${jobId}/topics`).then(r => r.json()),
        fetch(`/jobs/${jobId}/clauses`).then(r => r.json()),
        fetch(`/jobs/${jobId}/recommendations`).then(r => r.json()),
        fetch(`/jobs/${jobId}/insights`).then(r => r.json()),
        fetch(`/jobs/${jobId}/stakeholders`).then(r => r.json()),
        fetch(`/jobs/${jobId}/risk`).then(r => r.json()),
      ]);

    renderAllPanels(stats, structure, radio, topics, clauses, recs, insights, stakeholders, risk);
    enableDownloadButton(jobId);
  });

  eventSource.addEventListener('error', (e) => {
    const { message } = JSON.parse(e.data);
    showError(message);
    eventSource.close();
  });
}

// 4. DOWNLOAD
function downloadReport(jobId, format = 'json') {
  if (format === 'pdf') {
    window.location = `/jobs/${jobId}/report?format=pdf`;
  } else {
    fetch(`/jobs/${jobId}/report?format=json`)
      .then(r => r.json())
      .then(report => {
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report_${jobId}.json`;
        a.click();
      });
  }
}

// 5. ABORT
function abortJob(jobId) {
  fetch(`/jobs/${jobId}`, { method: 'DELETE' })
    .then(r => r.json())
    .then(({ status }) => {
      console.log('Job aborted:', status);
      location.reload();
    });
}
```

---

## ✅ Implementation Complete

All 16 endpoints are fully functional with:

- ✓ Request validation
- ✓ Proper HTTP status codes
- ✓ Detailed response models
- ✓ Mock/default data for testing
- ✓ Ready for real backend integration

Everything your frontend needs is here! 🎉
