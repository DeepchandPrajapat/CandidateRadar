import os
import json
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

# ── paths 
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_DIR     = os.path.join(BASE_DIR, "outputs2")
CHROMA_DIR   = os.path.join(BASE_DIR, "chroma_db")

# ── init embedding model 
print("⏳ Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Embedding model loaded")

# ── init ChromaDB persistent client 
chroma_client     = PersistentClient(path=CHROMA_DIR)
resume_collection = chroma_client.get_or_create_collection(
    name="resumes",
    metadata={"hnsw:space": "cosine"}   # cosine similarity
)


def build_embedding_text(resume: dict) -> str:

    parts = []

    # professional summary
    summary = resume.get("Professional Summary")
    if summary and summary != "Not mentioned":
        parts.append(summary)

    # total experience
    total_exp = resume.get("Total Experience")
    if total_exp and total_exp != "Not mentioned":
        parts.append(f"Total Experience: {total_exp}")

    # recent employer
    recent_employer = resume.get("Recent Employer")
    if recent_employer and recent_employer != "Not mentioned":
        parts.append(f"Recent Employer: {recent_employer}")

    # hard skills 
    skills = resume.get("Hard Skills", [])
    if skills and skills != ["Not mentioned"]:
        parts.append(f"Skills: {', '.join(skills)}")

    # job titles from employment history
    history = resume.get("Employment History", [])
    for job in history:
        title   = job.get("Job Title", "")
        company = job.get("Company Name", "")
        if title and title != "Not mentioned":
            parts.append(f"Job Title: {title} at {company}")

    # project descriptions
    projects = resume.get("Projects", [])
    for project in projects:
        name = project.get("Project Name", "")
        desc = project.get("Description", "")
        tech = project.get("Technologies Used", [])
        if desc and desc != "Not mentioned":
            parts.append(f"Project: {name}. {desc}")
        if tech and tech != ["Not mentioned"]:
            parts.append(f"Technologies: {', '.join(tech)}")

    return " | ".join(parts)


def index_single_resume(json_path: str) -> bool:

    json_filename = os.path.basename(json_path)

    candidate_id = json_filename.replace(".json", "")

    # check if already indexed
    existing = resume_collection.get(ids=[candidate_id])
    if existing and existing["ids"]:
        print(f"⏭️  Already indexed: {json_filename}")
        return False

    # load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        resume = json.load(f)

    # build embedding text (semantic fields only)
    embedding_text = build_embedding_text(resume)

    # generate embedding
    vector = embedding_model.encode(embedding_text).tolist()

    # store in ChromaDB with candidate ID
    resume_collection.add(
        ids       =[candidate_id],
        embeddings=[vector],
        documents =[embedding_text],
    )

    name = resume.get("Name", "Unknown")
    print(f"✅ Indexed: {name} (candidate_id: {candidate_id})")
    return True


def index_all_resumes() -> None:
    """
    Index all JSON files in outputs2/ folder into ChromaDB.
    Skips already-indexed files — safe to run multiple times.
    """
    if not os.path.exists(JSON_DIR):
        print(f"❌ JSON directory not found: {JSON_DIR}")
        return

    json_files = [f for f in os.listdir(JSON_DIR) if f.endswith(".json")]

    if not json_files:
        print("❌ No JSON files found in outputs2/")
        return

    print(f"\n📂 Found {len(json_files)} JSON files in outputs2/")
    print(f"📦 ChromaDB storing at: {CHROMA_DIR}\n")

    indexed = 0
    skipped = 0

    for filename in json_files:
        json_path = os.path.join(JSON_DIR, filename)
        result    = index_single_resume(json_path)
        if result:
            indexed += 1
        else:
            skipped += 1

    print(f"\n{'─'*50}")
    print(f"✅ Indexed : {indexed} resumes")
    print(f"⏭️  Skipped : {skipped} (already in ChromaDB)")
    print(f"📊 Total in ChromaDB: {resume_collection.count()}")


def get_collection():
    return resume_collection


def get_embedding_model():
    return embedding_model


if __name__ == "__main__":
    index_all_resumes()