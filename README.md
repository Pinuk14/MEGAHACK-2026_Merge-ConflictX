# Merge-ConflictX

## Automation + Quiz Solving with Ollama

The backend automation routes now support LLM-based planning via Ollama with safe deterministic fallback.

### Endpoints

- `POST /automation_plan`: returns executable browser actions for general automation commands.
- `POST /quiz_solve`: returns selected quiz answers + executable click actions (including submit click when detected).

### Ollama Configuration

Set these environment variables before starting the backend:

- `OLLAMA_BASE_URL` (default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (default: `llama3.2:3b`)
- `OLLAMA_TIMEOUT_SECONDS` (default: `60`)
- `OLLAMA_MAX_RETRIES` (default: `2`)

If Ollama is unavailable or returns invalid JSON, backend falls back to deterministic logic.

### Quick Run Checklist

1. Start Ollama and pull your model.
2. Start backend API.
3. Reload Chrome extension.
4. On a quiz page, click **Analyze** in popup.
5. Flow:
	- Scraper extracts page + quiz structure.
	- Backend `/analyze` runs content analysis.
	- Backend `/quiz_solve` generates answer actions.
	- Extension executes option clicks + submit action.

### Notes

- Keep action schema strict: `TYPE`, `CLICK`, `SELECT`, `NAVIGATE`, `DOWNLOAD`, `SCROLL`.
- LLM outputs are validated before execution.
- Failed/invalid LLM outputs never execute directly; fallback planner is used.
