
## Backend setup

```bash
cd server   # or your backend folder name

# with uv (recommended)
uv sync
# or: uv pip install -r requirements.txt
# or: pip install -r requirements.txt

# Ollama cloud model (local daemon)
ollama signin
ollama pull gpt-oss:120b-cloud

uv run main.py
# Flask serves http://127.0.0.1:5001
```

### API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/lecture/generate` | Body: `{ "topic", "audience_level?", "num_slides?", "model?" }` |
| GET | `/lecture/<id>` | Fetch saved lecture JSON |
| POST | `/lecture/export` | Body: `{ "lecture_id" }` → downloads `lecture.pptx` |
| GET | `/charts/<filename>` | Chart PNG for a slide |
| GET | `/health` | Health check |

Default model: `gpt-oss:120b-cloud`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
# Vite serves http://localhost:5173
```

The frontend calls the Flask API at `http://localhost:5001` (see `src/api.ts`).

## Usage

1. Start Ollama (if not already running) and ensure you are signed in for cloud models.
2. Start the backend: `uv run main.py` in `server/`.
3. Start the frontend: `npm run dev` in `frontend/`.
4. Open http://localhost:5173
5. Enter a topic (e.g. `K-Nearest Neighbors and K-Means`), pick audience level, click **Generate Lecture**.
6. Navigate slides, read speaker notes, export PPTX when ready.

## How generation works

1. Flask receives the topic and calls `generate_lecture()` in `generator.py`.
2. Ollama is called with `format=Lecture.model_json_schema()` and `think=False`.
3. System prompt includes `Reasoning: low` so gpt-oss spends less time in the
   Harmony **analysis** channel and more on a clean **final** answer.
4. Response is cleaned:
   - Strip Harmony channel markers (`<|channel|>analysis...`, etc.)
   - Extract JSON body (including from markdown fences if present)
   - Normalize common field aliases (`lecture_title` → `title`, code string → object, etc.)
5. Pydantic validates the result; failed attempts retry (default 2).
6. Charts are rendered with matplotlib; lecture JSON is saved for export/reload.

## gpt-oss / Harmony notes

`gpt-oss:120b-cloud` uses OpenAI’s Harmony response format. If left unmanaged it can:

- Dump chain-of-thought or markdown instead of JSON
- Leak channel tags into the content field

This project mitigates that with:

- `Reasoning: low` in the system prompt
- `think=False` on the chat call
- `_strip_harmony_artifacts()` + `_extract_json()` + `_normalize_lecture_dict()`
- Retries with logged raw previews: look for `[generate_lecture] attempt ...` in the server terminal

If generation still fails, check the raw content preview in the Flask logs for
stray `<|channel|>` tags or non-JSON prose.

## Environment

Optional (not required for local-daemon cloud models after `ollama signin`):

```bash
# Only if you intentionally call the Ollama Cloud HTTP API directly
# export OLLAMA_API_KEY=...
```

## Troubleshooting

| Symptom | What to check |
|---|---|
| `Invalid JSON: expected value at line 1 column 1` | Confirm `generator.py` has `HARMONY_CHANNEL_PATTERN` and a retry loop — not a bare `model_validate_json` |
| Model not found | `ollama pull gpt-oss:120b-cloud` and `ollama list` |
| Auth / cloud access | `ollama signin` then retry |
| CORS / frontend can’t reach API | Backend on port 5001; frontend `api.ts` base URL matches |
| Charts missing | Ensure `generated_charts/` is writable; check `/charts/<file>` |

## License

Private / project use as you prefer.