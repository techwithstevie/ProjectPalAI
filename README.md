# ProjectPalAI

**Learn by building.** ProjectPalAI turns any project idea into a YouTube-style, step-by-step build tutorial—with a full spoken transcript, on-screen key points, and working code that lands in a real repo.

No slide decks. No multi-module courses. One product, linear steps, modern stack and best practices.

---

## What it does

1. Describe **what to build** (e.g. *CLI todo app with SQLite*).
2. Pick **difficulty** (beginner / intermediate / advanced) and **size** (small / medium / monolithic).
3. ProjectPalAI generates a complete tutorial:
   - Project brief, stack, repo layout, and learning outcomes
   - Ordered **build steps** with goals, bullets, and code
   - **Full spoken transcripts** (read while you code)
   - Checkpoints, final project code, and how-to-run instructions
   - Optional stretch **challenges** with solutions
4. Follow steps in the three-column studio UI, or export a PPTX for offline use.

---

## Product model

| Control | Options | Effect |
|--------|---------|--------|
| **Topic** | Free text | What the project is |
| **Difficulty** | beginner · intermediate · advanced | Depth of explanation and APIs |
| **Size** | small · medium · monolithic | Number of steps and scope |

| Size | Typical steps | Rough time |
|------|---------------|------------|
| Small | ~8–12 | 2–4 hours |
| Medium | ~14–20 | 6–12 hours |
| Monolithic | ~24–36 | 20–40 hours |

**Removed by design:** charts/graphs, multi-module courses, milestone/module pickers, paper-style slides.

---

## Studio layout


- **Left** — Project overview, step list, challenges  
- **Center** — Transcript you can read aloud while building  
- **Right** — Bullets, files touched, code blocks, expected output  

---

## Stack

### Backend (`server/`)

| Piece | Role |
|-------|------|
| **FastAPI** | REST + SSE streaming |
| **Pydantic** | Tutorial schema |
| **Ollama** | Local/cloud LLM generation |
| **python-pptx** | PPTX export (no charts) |
| **Python 3.12+** | Runtime |

### Frontend (`frontend/`)

| Piece | Role |
|-------|------|
| **React + TypeScript + Vite** | UI |
| **DM Sans · Fraunces · JetBrains Mono** | Typography |
| Teal + violet on charcoal | Brand theme |

---

## Project structure

projectpalai/
├── README.md
├── server/
│ ├── main.py # FastAPI app (ProjectPalAI API)
│ ├── generator.py # LLM tutorial generation
│ ├── schema.py # ProjectTutorial models
│ ├── pptx_export.py # PPTX export
│ ├── pyproject.toml
│ ├── generated_tutorials/ # Saved JSON tutorials
│ └── exports/ # PPTX files
└── frontend/
├── index.html
├── public/favicon.svg
└── src/
├── App.tsx
├── api.ts
├── index.css
├── main.tsx
├── types/course.ts
└── components/
├── StepSidebar.tsx
├── TranscriptStage.tsx
└── StepRail.tsx


---

## Prerequisites

- **Python 3.12+**
- **Node.js 18+** (and npm)
- **[Ollama](https://ollama.com)** running, with a model available  
  (default in code: `gpt-oss:120b-cloud` — change in `generator.py` if needed)

```bash
# Example: pull a local model if you use one
ollama pull llama3.2
```

---

## Setup

### Backend

```bash
cd server
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
# or: pip install -e ".[dev]"

uvicorn main:app --host 0.0.0.0 --port 5001 --reload
```

- API base: `http://localhost:5001`
- Health: `GET http://localhost:5001/health`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: usually `http://localhost:5173`

Optional env (frontend):

```bash
# frontend/.env
VITE_API_URL=http://localhost:5001
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/generate` | Generate tutorial (sync JSON) |
| `POST` | `/api/generate/stream` | Generate with SSE status + final tutorial |
| `GET` | `/api/tutorials` | List saved tutorials |
| `GET` | `/api/tutorials/{id}` | Load one tutorial |
| `GET` | `/api/tutorials/{id}/export` | Download PPTX |

Legacy aliases (same handlers):

- `GET /api/courses/{id}`
- `GET /api/courses/{id}/export`

### Generate body

```json
{
  "topic": "CLI todo app with SQLite",
  "difficulty": "beginner",
  "size": "small"
}
```

Legacy fields still accepted: `audience_level`, `project_size`.

### Stream events (SSE)

```text
data: {"type": "status", "message": "..."}
data: {"type": "complete", "tutorial": { ... }}
data: {"type": "error", "message": "..."}
```

---

## Tutorial schema (concept)

Each generated tutorial is a **ProjectTutorial**:

- **Meta** — title, tagline, difficulty, size, estimated hours  
- **Brief** — problem statement, end state, prerequisites, learning outcomes  
- **Engineering** — repo layout, stack (name / version / purpose), best practices  
- **Body** — intro transcript → ordered **steps** → outro transcript  
- **Each step** — title, goal, bullets, speaker notes, code (`file_path` + body), files touched, checkpoint flag  
- **Ship** — final project code, how to run  
- **Extras** — challenges with solutions  

Generation targets **current** practices (Python 3.12+, `pyproject.toml`, type hints, modern library APIs—not legacy patterns).

---

## Usage tips

1. **Be specific** in the topic: stack, features, and constraints improve results.  
2. Start with **small** + **beginner** to validate the pipeline, then scale size.  
3. Use **checkpoints** as natural “pause and run” moments.  
4. Export **PPTX** when you want notes and code offline (speaker notes carry the transcript).  

---

## Configuration

| Where | What |
|-------|------|
| `server/generator.py` | Default Ollama `model`, size → step targets, system prompt / modern stack rules |
| `server/main.py` | Host/port (default `5001`), CORS, storage dirs |
| `frontend/src/api.ts` | `VITE_API_URL` / default `http://localhost:5001` |

---

## Development

```bash
# Backend tests / lint (optional deps)
cd server
pip install -e ".[dev]"
ruff check .
pytest

# Frontend
cd frontend
npm run build
npm run preview
```

---

## Design notes

- **Brand:** ProjectPalAI — charcoal base, teal primary, violet AI accent  
- **UX:** Transcript is the hero (center); bullets and code support the build (right rail)  
- **Pedagogy:** Tutorial-style teaching only—every step advances one shared project  

---

## License

MIT

---

## Tagline

**ProjectPalAI — Build · Learn · Ship.**