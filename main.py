from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes import resume, search

app = FastAPI(
    title="CandidateRadar",
    description="AI-powered resume screening using RAG and Gemini",
    version="1.0.0"
)

# allow frontend (Netlify etc) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router, prefix="/resume", tags=["Resume"])
app.include_router(search.router, prefix="/search", tags=["Search"])


@app.get("/")
def root():
    return {"message": "CandidateRadar API is running"}