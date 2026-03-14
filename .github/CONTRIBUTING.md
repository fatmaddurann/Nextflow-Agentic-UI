# Contributing to Nextflow-Agentic-UI

Thank you for considering contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/fatmaddurann/Nextflow-Agentic-UI.git
cd Nextflow-Agentic-UI

# Configure environment
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY

# Start the full stack
docker compose up -d
```

## Project Structure

See [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for a full breakdown.

## Backend Development

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Frontend Development

```bash
cd frontend
npm install
npm run dev   # starts at http://localhost:5173
```

## Nextflow Pipeline Testing

```bash
cd pipeline
nextflow run main.nf -profile test -stub-run   # no real data needed
```

## Pull Request Guidelines

- Create a feature branch: `git checkout -b feat/my-feature`
- Keep commits focused and atomic
- Add tests where possible
- Update documentation for any API or pipeline changes
- Ensure `docker compose up` still works end-to-end

## Code Style

- **Python**: PEP 8, async preferred, type hints on public functions
- **React**: functional components, hooks, Tailwind utility classes
- **Nextflow**: DSL2 modules, explicit input/output declarations

## Adding Knowledge Base Articles

Edit `backend/rag/knowledge_base.py` — add a dict to `KNOWLEDGE_BASE`:

```python
{
    "id":       "mymodule-001",
    "title":    "MyTool: Descriptive Error Title",
    "category": "mytool_errors",
    "tags":     ["mytool", "keyword1"],
    "content":  "Problem: ...\nCause: ...\nSolution:\n1. ...",
    "source":   "Tool documentation URL"
}
```

The article will be automatically embedded and indexed on next startup.
