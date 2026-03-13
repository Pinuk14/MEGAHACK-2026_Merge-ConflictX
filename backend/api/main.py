from fastapi import FastAPI

from backend.api.routes.analysis import router as analysis_router
from backend.api.routes.ingestion import router as ingestion_router

app = FastAPI(title="Merge-ConflictX API", version="1.0.0")


@app.get("/")
def root() -> dict:
    return {"message": "Welcome to the Merge-ConflictX API. Use /docs for API documentation."}


@app.get("/health")
def health() -> dict:
	return {"status": "ok"}


app.include_router(ingestion_router)
app.include_router(analysis_router)
