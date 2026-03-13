from fastapi import FastAPI

from backend.api.routes.analysis import router as analysis_router
from backend.api.routes.automation import router as automation_router
from backend.api.routes.ingestion import router as ingestion_router

app = FastAPI(title="Merge-ConflictX API", version="1.0.0")


@app.get("/health")
def health() -> dict:
	return {"status": "ok"}


app.include_router(ingestion_router)
app.include_router(analysis_router)
app.include_router(automation_router)
