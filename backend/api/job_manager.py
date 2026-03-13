"""Job management system for tracking pipeline jobs."""
import asyncio
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, List, Any
from uuid import uuid4
import json
import time
from dataclasses import dataclass, asdict, field
from backend.api.models import JobStatus, PipelinePhase
import io
import importlib
import re
import zipfile


@dataclass
class JobData:
    """Stores all data for a job."""
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    current_step: Optional[str] = None
    elapsed_seconds: int = 0
    input_file_id: Optional[str] = None
    input_text: Optional[str] = None
    
    # SSE event history (for reconnects)
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    # Endpoint data caches
    stats: Dict[str, Any] = field(default_factory=dict)
    structure: Dict[str, Any] = field(default_factory=dict)
    radio_comms: List[Dict[str, str]] = field(default_factory=list)
    topics: List[Dict[str, Any]] = field(default_factory=list)
    clauses: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    insights: List[Dict[str, Any]] = field(default_factory=list)
    stakeholders: List[Dict[str, Any]] = field(default_factory=list)
    risk: Dict[str, Any] = field(default_factory=dict)
    
    # Report data
    report_json: Optional[Dict[str, Any]] = None
    report_pdf: Optional[bytes] = None
    
    # Error tracking
    error: Optional[str] = None


class JobManager:
    """Manages job lifecycle and state."""
    
    def __init__(self):
        """Initialize job manager."""
        self._jobs: Dict[str, JobData] = {}
        self._file_storage: Path = Path(__file__).resolve().parents[2] / "infrastructure" / "storage" / "uploads"
        self._file_storage.mkdir(parents=True, exist_ok=True)
        self._job_file_counter = 0
    
    def create_job(self, input_text: Optional[str] = None, file_id: Optional[str] = None) -> str:
        """Create a new job and return job_id."""
        job_id = str(uuid4())
        job = JobData(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=datetime.now(),
            input_text=input_text,
            input_file_id=file_id,
        )
        self._jobs[job_id] = job
        return job_id
    
    def get_job(self, job_id: str) -> Optional[JobData]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: JobStatus):
        """Update job status."""
        if job_id in self._jobs:
            self._jobs[job_id].status = status
            if status == JobStatus.DONE:
                self._jobs[job_id].completed_at = datetime.now()
    
    def set_current_step(self, job_id: str, step: str):
        """Set current step."""
        if job_id in self._jobs:
            self._jobs[job_id].current_step = step
    
    def add_event(self, job_id: str, event_type: str, data: Dict[str, Any]):
        """Add SSE event to job history."""
        if job_id in self._jobs:
            self._jobs[job_id].events.append({
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            })
    
    def set_stats(self, job_id: str, stats: Dict[str, Any]):
        """Set stats data."""
        if job_id in self._jobs:
            self._jobs[job_id].stats = stats
    
    def set_structure(self, job_id: str, structure: Dict[str, Any]):
        """Set structure data."""
        if job_id in self._jobs:
            self._jobs[job_id].structure = structure
    
    def set_radio_comms(self, job_id: str, comms: List[Dict[str, str]]):
        """Set radio communications."""
        if job_id in self._jobs:
            self._jobs[job_id].radio_comms = comms
    
    def set_topics(self, job_id: str, topics: List[Dict[str, Any]]):
        """Set topics."""
        if job_id in self._jobs:
            self._jobs[job_id].topics = topics
    
    def set_clauses(self, job_id: str, clauses: List[Dict[str, Any]]):
        """Set clauses."""
        if job_id in self._jobs:
            self._jobs[job_id].clauses = clauses
    
    def set_recommendations(self, job_id: str, recommendations: List[Dict[str, Any]]):
        """Set recommendations."""
        if job_id in self._jobs:
            self._jobs[job_id].recommendations = recommendations
    
    def set_insights(self, job_id: str, insights: List[Dict[str, Any]]):
        """Set insights."""
        if job_id in self._jobs:
            self._jobs[job_id].insights = insights
    
    def set_stakeholders(self, job_id: str, stakeholders: List[Dict[str, Any]]):
        """Set stakeholders."""
        if job_id in self._jobs:
            self._jobs[job_id].stakeholders = stakeholders
    
    def set_risk(self, job_id: str, risk: Dict[str, Any]):
        """Set risk data."""
        if job_id in self._jobs:
            self._jobs[job_id].risk = risk
    
    def set_report_json(self, job_id: str, report: Dict[str, Any]):
        """Set JSON report."""
        if job_id in self._jobs:
            self._jobs[job_id].report_json = report
    
    def set_report_pdf(self, job_id: str, pdf_bytes: bytes):
        """Set PDF report."""
        if job_id in self._jobs:
            self._jobs[job_id].report_pdf = pdf_bytes
    
    def set_error(self, job_id: str, error: str):
        """Set error for job."""
        if job_id in self._jobs:
            self._jobs[job_id].error = error
            self._jobs[job_id].status = JobStatus.FAILED
    
    def abort_job(self, job_id: str):
        """Abort a job (mark as failed)."""
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.FAILED
            self._jobs[job_id].error = "Job aborted by user"
            self._jobs[job_id].completed_at = datetime.now()
    
    def save_uploaded_file(self, filename: str, content: bytes) -> str:
        """Save uploaded file and return file_id."""
        file_id = f"file_{uuid4().hex[:8]}"
        file_path = self._file_storage / f"{file_id}_{filename}"
        file_path.write_bytes(content)
        return file_id

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Normalize extracted text and drop control characters."""
        if not text:
            return ""
        cleaned = text.replace("\x00", " ")
        cleaned = re.sub(r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _is_low_quality_text(text: str) -> bool:
        """Heuristic check for binary-like/gibberish extraction output."""
        if not text or len(text) < 40:
            return True

        sample = text[:4000]
        printable = sum(1 for c in sample if c.isprintable())
        alpha = sum(1 for c in sample if c.isalpha())
        weird_markers = ["obj", "endobj", "stream", "endstream", "xref", "/filter", "/length"]
        marker_hits = sum(sample.lower().count(m) for m in weird_markers)

        printable_ratio = printable / max(len(sample), 1)
        alpha_ratio = alpha / max(len(sample), 1)

        return printable_ratio < 0.9 or alpha_ratio < 0.2 or marker_hits > 10
    
    def get_uploaded_file(self, file_id: str) -> Optional[str]:
        """Get uploaded file content by file_id."""
        for path in self._file_storage.glob(f"{file_id}_*"):
            if path.is_file():
                suffix = path.suffix.lower()
                if suffix == ".pdf":
                    try:
                        pdfplumber = importlib.import_module("pdfplumber")
                        with pdfplumber.open(io.BytesIO(path.read_bytes())) as pdf:
                            pages = [(p.extract_text() or "") for p in pdf.pages]
                        text = self._sanitize_text("\n".join(pages))
                        if text and not self._is_low_quality_text(text):
                            return text
                    except Exception:
                        pass

                    # PDF exists but no extractable text (e.g., scanned image-only PDF)
                    return ""

                if suffix in {".txt", ".xml", ".json"}:
                    text = self._sanitize_text(path.read_text(encoding="utf-8", errors="ignore"))
                    if self._is_low_quality_text(text):
                        return ""
                    return text

                if suffix == ".docx":
                    try:
                        with zipfile.ZipFile(path) as zf:
                            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
                        # Strip XML tags to plain text.
                        xml = re.sub(r"</w:p>", "\n", xml)
                        text = re.sub(r"<[^>]+>", " ", xml)
                        text = self._sanitize_text(text)
                        return text
                    except Exception:
                        return ""

                if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
                    try:
                        ocr_mod = importlib.import_module("backend.cleaning.ocr_module")
                        ocr = ocr_mod.OCRModule()
                        text = self._sanitize_text(ocr.extract_text_from_image_path(path))
                        return text
                    except Exception:
                        return ""

                if suffix == ".wav":
                    try:
                        sf = importlib.import_module("soundfile")
                        info = sf.info(str(path))
                        duration = float(info.frames) / float(info.samplerate or 1)
                        return self._sanitize_text(
                            f"Audio file metadata: duration {duration:.2f}s, sample_rate {info.samplerate}Hz, channels {info.channels}."
                        )
                    except Exception:
                        return ""

                text = self._sanitize_text(path.read_text(encoding="utf-8", errors="ignore"))
                if self._is_low_quality_text(text):
                    return ""
                return text
        return None


# Global job manager instance
_job_manager = JobManager()


def get_job_manager() -> JobManager:
    """Get the global job manager."""
    return _job_manager
