import os
import re
import json
import hashlib
import psycopg2
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL")
print(repr(DB_URL))


def get_connection():
    return psycopg2.connect(DB_URL)


_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("⏳ Loading embedding model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✅ Embedding model loaded")
    return _embedding_model


def get_file_hash(file_path: str) -> str:
    """Generate md5 hash of file content — used for duplicate detection."""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def build_embedding_text(resume: dict) -> str:
    """Build searchable text for semantic embedding. No names/emails/ids."""
    parts = []

    summary = resume.get("Professional Summary")
    if summary and summary != "Not mentioned":
        parts.append(summary)

    total_exp = resume.get("Total Experience")
    if total_exp and total_exp != "Not mentioned":
        parts.append(f"Total Experience: {total_exp}")

    skills = resume.get("Hard Skills", [])
    if skills and skills != ["Not mentioned"]:
        parts.append(f"Skills: {', '.join(skills)}")

    history = resume.get("Employment History", [])
    for job in history:
        title = job.get("Job Title", "")
        company = job.get("Company Name", "")
        if title and title != "Not mentioned":
            parts.append(f"Job Title: {title} at {company}")

        responsibilities = job.get("Responsibilities", [])
        if responsibilities and responsibilities != ["Not mentioned"]:
            parts.append("Responsibilities: " + " ".join(responsibilities))

    projects = resume.get("Projects", [])
    for project in projects:
        if not isinstance(project, dict):
            continue
        name = project.get("Project Name", "")
        desc = project.get("Description", "")
        tech = project.get("Technologies Used", [])

        if name and name != "Not mentioned":
            parts.append(f"Project: {name}")
        if desc and desc != "Not mentioned":
            parts.append(desc)
        if tech and tech != ["Not mentioned"]:
            parts.append("Technologies: " + ", ".join(tech))

    return " | ".join(parts)


def parse_experience_years(exp_str: str) -> float:
    """Convert '4+ years', '8 years 3 months' etc into a float."""
    if not exp_str or exp_str == "Not mentioned":
        return 0.0

    exp_str = exp_str.lower()
    match = re.search(r'(\d+\.?\d*)\s*year', exp_str)
    years = float(match.group(1)) if match else 0.0

    match_months = re.search(r'(\d+)\s*month', exp_str)
    months = float(match_months.group(1)) / 12 if match_months else 0.0

    return round(years + months, 2)


def index_single_resume(resume: dict, file_hash: str, resume_file_url: str = None) -> int | None:
    """
    Insert one parsed resume into Supabase.
    Returns the new row's id if inserted, None if skipped (duplicate).
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        # check for duplicate via file_hash
        cur.execute("SELECT id FROM candidates WHERE file_hash = %s", (file_hash,))
        existing = cur.fetchone()
        if existing:
            print(f"⏭️  Already indexed (duplicate file): id {existing[0]}")
            return None

        embedding_text = build_embedding_text(resume)
        vector = get_embedding_model().encode(embedding_text).tolist()

        name             = resume.get("Name", "Unknown")
        email            = resume.get("Contact Information", {}).get("Email", "Not mentioned")
        phone            = resume.get("Contact Information", {}).get("Phone", "Not mentioned")
        recent_employer  = resume.get("Recent Employer", "Not mentioned")
        total_experience = resume.get("Total Experience", "Not mentioned")
        experience_years = parse_experience_years(total_experience)
        skills           = resume.get("Hard Skills", [])
        if skills == ["Not mentioned"]:
            skills = []

        cur.execute("""
            INSERT INTO candidates (
                name, email, phone, recent_employer,
                total_experience, experience_years, skills,
                resume_file_url, full_json, embedding, file_hash
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id
        """, (
            name, email, phone, recent_employer,
            total_experience, experience_years, skills,
            resume_file_url, json.dumps(resume), vector, file_hash
        ))

        new_id = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Indexed: {name} (id: {new_id})")
        return new_id

    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to index resume: {e}")
        return None

    finally:
        cur.close()
        conn.close()


def index_resume_from_json_file(json_path: str, resume_file_url: str = None) -> int | None:
    """Load a JSON file from disk, hash it, and index it into Supabase."""
    file_hash = get_file_hash(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        resume = json.load(f)

    return index_single_resume(resume, file_hash, resume_file_url)


def index_all_from_folder(json_dir: str) -> None:
    """Bulk index all JSON files from a local folder into Supabase."""
    if not os.path.exists(json_dir):
        print(f"❌ Folder not found: {json_dir}")
        return

    json_files = [f for f in os.listdir(json_dir) if f.endswith(".json")]

    if not json_files:
        print("❌ No JSON files found.")
        return

    print(f"\n📂 Found {len(json_files)} JSON files\n")

    indexed = 0
    skipped = 0

    for filename in json_files:
        json_path = os.path.join(json_dir, filename)
        result = index_resume_from_json_file(json_path)
        if result is not None:
            indexed += 1
        else:
            skipped += 1

    print(f"\n{'─'*50}")
    print(f"✅ Indexed : {indexed}")
    print(f"⏭️  Skipped : {skipped}")


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    JSON_DIR = os.path.join(BASE_DIR, "outputs2")
    index_all_from_folder(JSON_DIR)