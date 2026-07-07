# CandidateRadar 🎯

A RAG-powered resume intelligence system that parses resumes, stores them as searchable vectors, and lets recruiters find the best-fit candidates using natural language — with LLM-generated ranking and reasoning.

**🔗 Live demo:** https://candidateradar.netlify.app/
**⚙️ API + Swagger docs:** https://candidateradar.onrender.com/docs

> Note: the backend is on Render's free tier, so the first request after inactivity can take ~30s to wake up.

---

## What it does

1. **Upload** — recruiters drag and drop resumes (PDF/DOCX). Each resume is parsed by Gemini into structured JSON (name, skills, experience, education, total years).
2. **Store** — parsed data + embeddings are stored in Supabase (Postgres + pgvector), original files in Supabase Storage.
3. **Search** — type a job description or requirement in plain English. The system does semantic vector search over all stored candidates, then Gemini ranks the top matches with reasoning for each — fit, concerns, and estimated years of relevant experience.

This isn't just "call an LLM API" — it's a full **RAG (Retrieval-Augmented Generation) pipeline**: extraction → embedding → semantic search (retrieval) → LLM-based ranking (generation).

---

## Architecture

```
                     ┌─────────────────────┐
                     │   Frontend (Netlify) │
                     │  Landing / Upload /  │
                     │     Search pages     │
                     └──────────┬───────────┘
                                │  (proxy.js — Netlify Function)
                                │  hides API key from browser
                                ▼
                     ┌─────────────────────┐
                     │  Backend (Render)   │
                     │  FastAPI, Dockerized│
                     └──────────┬───────────┘
                       │                  │
            resume parsing         semantic search
            (Gemini API)           + ranking (Gemini)
                       │                  │
                       ▼                  ▼
                 ┌───────────────────────────────┐
                 │        Supabase                │
                 │  Postgres + pgvector (search)  │
                 │  Supabase Storage (resume files)│
                 └───────────────────────────────┘
```

**Security:** the frontend never talks to Render directly or holds an API key. It calls a Netlify serverless function (`proxy.js`), which holds the key server-side and forwards requests — so only the deployed frontend (not clones of the repo) can hit the upload endpoint.

---

## Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI (Python), Dockerized |
| LLM | Google Gemini (parsing + ranking) |
| Vector search | Supabase (Postgres + pgvector) |
| File storage | Supabase Storage |
| Frontend | HTML / CSS / JS, dark mode UI |
| Frontend hosting | Netlify (with a serverless proxy function) |
| Backend hosting | Render |

---

## Features

- ✅ Resume parsing (PDF + DOCX) into structured JSON via Gemini
- ✅ Semantic search over resumes using pgvector
- ✅ Hybrid filtering (SQL + vector similarity)
- ✅ Gemini-based candidate ranking with written reasoning per candidate
- ✅ File upload to Supabase Storage, linked back to each candidate record
- ✅ FastAPI backend with auto-generated Swagger UI
- ✅ API key protected via a Netlify proxy function (no exposed secrets in frontend code)
- ✅ Fully deployed: frontend on Netlify, backend on Render, DB on Supabase

---

## Project structure

```
CandidateRadar/
├── api.py                     # FastAPI app — main entry point
├── batch_parse.py              # one-time migration: bulk parse local resumes
├── src/
│   ├── rag/
│   │   └── embedder.py         # one-time migration: bulk index JSONs into Supabase
│   └── ...
├── frontend/
│   ├── index.html               # landing page
│   ├── upload.html / upload.js  # upload page
│   ├── search.html / search.js  # search page
│   ├── netlify.toml
│   └── netlify/
│       └── functions/
│           └── proxy.js         # hides API key, forwards requests to Render
├── Dockerfile
├── requirements.txt
└── README.md
```

> `batch_parse.py` and `embedder.py`'s `index_all_from_folder()` were one-time tools used to migrate the initial local dataset into Supabase. They're kept in the repo for reference but aren't part of the live request flow — resume ingestion in production goes through `POST /resume/upload`.

---

## API endpoints (see live Swagger docs for full schema)

- `POST /resume/upload` — upload a resume, parse it, store it in Supabase
- `GET /search` (or `/api`) — semantic search + Gemini ranking against stored candidates

Full interactive documentation: https://candidateradar.onrender.com/docs

---

## Running locally

```bash
git clone <your-repo-url>
cd CandidateRadar
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

Create a `.env` file with:

```
GEMINI_API_KEY=your_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_DB_URL=your_supabase_db_url
```

Run the API:

```bash
python api.py
```

Visit `http://localhost:8000/docs` for the Swagger UI.

---

## Why this project

Built to go beyond "wrap an LLM API in a Flask app" — this covers the full AI engineering stack: structured extraction from unstructured documents, vector embeddings, semantic retrieval, and LLM-based reasoning over retrieved results, all wrapped in a production-style deployment (Dockerized API, managed Postgres + pgvector, serverless proxy for security).