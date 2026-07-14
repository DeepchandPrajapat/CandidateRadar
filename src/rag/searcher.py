import os
import json
import psycopg2
import numpy as np
from google import genai
from google.genai import types
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector

from src.rag.query_parser import parse_query
from src.rag.embedder import get_embedding_model

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

DB_URL = os.getenv("SUPABASE_DB_URL")
print(f"DEBUG: DB_URL = {DB_URL[:50]}")


def get_connection():
    conn = psycopg2.connect(DB_URL)
    register_vector(conn)
    return conn


# ── Step 1: Single SQL query — filter + semantic search together ──────────────

def search_candidates(parsed_query: dict, top_n: int = 3) -> list[dict]:
    semantic_query = parsed_query.get("semantic_query", "")
    query_vector = get_embedding_model().encode(semantic_query).tolist()

    # Debug: basic vector properties
    print(f"DEBUG: vector dims = {len(query_vector)}")
    print(f"DEBUG: has nan = {any(np.isnan(x) for x in query_vector)}")
    print(f"DEBUG: has inf = {any(np.isinf(x) for x in query_vector)}")
    print(f"DEBUG: vector norm = {np.linalg.norm(query_vector)}")

    # Build vector string for SQL literal
    vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"
    

    # Extract filters from parsed query
    skills = parsed_query.get("skills", [])
    min_experience = parsed_query.get("min_experience", None)
    location = parsed_query.get("location", None)
    recent_employer = parsed_query.get("recent_employer", None)

    conditions = []
    params = {}

    # Skill filter – optional, uncomment to enable
    # if skills:
    #     conditions.append("skills && %(skills)s")
    #     params["skills"] = skills

    if min_experience is not None:
        conditions.append("experience_years >= %(min_exp)s")
        params["min_exp"] = min_experience

    if location:
        conditions.append("location ILIKE %(location)s")
        params["location"] = f"%{location}%"

    if recent_employer:
        conditions.append("recent_employer ILIKE %(employer)s")
        params["employer"] = f"%{recent_employer}%"

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT
            id, name, email, phone, recent_employer,
            total_experience, experience_years, skills,
            resume_file_url, full_json,
            1 - (embedding <=> '{vector_str}'::vector) AS similarity
        FROM candidates
        {where_clause}
        ORDER BY embedding <=> '{vector_str}'::vector
        LIMIT {top_n}
    """
    print(f"DEBUG: FULL SQL >>> {sql}")
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Count total candidates
        cur.execute("SELECT COUNT(*) FROM candidates")
        count = cur.fetchone()[0]
        print(f"DEBUG: total candidates in DB = {count}")
        print(f"DEBUG: where_clause = '{where_clause}'")

        # Execute search
        cur.execute(sql)
        rows = cur.fetchall()
        print(f"DEBUG: rows fetched = {len(rows)}")

        columns = [desc[0] for desc in cur.description]
        results = [dict(zip(columns, row)) for row in rows]
        return results

    except Exception as e:
        print(f"❌ Search query failed: {e}")
        return []

    finally:
        cur.close()
        conn.close()


# ── Step 2: Rank with Gemini — returns structured JSON ─────────────────────────

def _strip_code_fences(text: str) -> str:
    """Gemini sometimes wraps JSON in ```json ... ``` even in JSON mode. Strip it."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return cleaned.strip()


def _fallback_ranking(candidates: list[dict]) -> list[dict]:
    """Used if Gemini call or JSON parsing fails."""
    fallback = []
    rank_num = 1
    for c in candidates:
        fallback.append({
            "id": c.get("id"),
            "rank": rank_num,
            "why": "Automatic fallback ranking — ordered by semantic similarity.",
            "fit": f"{c.get('total_experience') or 'Experience not specified'}, last at {c.get('recent_employer') or 'unknown employer'}.",
            "concerns": "Not evaluated.",
            "experience": c.get("total_experience"),
        })
        rank_num += 1
    return fallback


def rank_with_gemini(candidates: list[dict], original_query: str) -> list[dict]:
    """Send candidates to Gemini for ranking. Returns a list of dicts with ranking fields."""
    if not candidates:
        return []

    candidate_summaries = []
    for c in candidates:
        full_json = c.get("full_json", {})
        if isinstance(full_json, str):
            full_json = json.loads(full_json)

        employment_list = []
        for job in full_json.get("Employment History", []):
            employment_list.append({
                "company": job.get("Company Name"),
                "title": job.get("Job Title"),
                "duration": job.get("Duration"),
            })

        projects_list = []
        for p in full_json.get("Projects", []):
            if not isinstance(p, dict):
                continue
            projects_list.append({
                "name": p.get("Project Name"),
                "tech": p.get("Technologies Used", []),
                "duration": p.get("Duration", "Not mentioned"),
            })

        summary = {
            "id": c.get("id"),
            "name": c.get("name"),
            "total_experience": c.get("total_experience"),
            "recent_employer": c.get("recent_employer"),
            "skills": c.get("skills", [])[:15],
            "summary": full_json.get("Professional Summary", "")[:300],
            "employment": employment_list,
            "projects": projects_list,
        }
        candidate_summaries.append(summary)

    prompt = f"""You are an expert technical recruiter. Rank these candidates for the following job requirement.

Job Requirement: "{original_query}"

Candidates:
{json.dumps(candidate_summaries, indent=2)}

Rank ALL candidates from best to worst fit. Be specific but concise — 1-2 sentences max per field.

Return a JSON array. Each element must have EXACTLY these fields, and "id" must exactly match
the "id" value given for that candidate above (do not invent or renumber ids):

[
  {{
    "id": <candidate's original id, integer>,
    "rank": <integer, 1 = best fit>,
    "why": "1-2 sentences explaining why ranked here vs others",
    "fit": "specific matching skills and experience, 1 sentence",
    "concerns": "main gap, 1 sentence",
    "experience": "X years in the specific skill mentioned in the requirement"
  }}
]

Return ONLY the JSON array. No markdown, no explanation, no extra text.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        cleaned = _strip_code_fences(response.text)
        ranking_list = json.loads(cleaned)
        if not isinstance(ranking_list, list):
            raise ValueError("Gemini did not return a JSON array")
        return ranking_list
    except Exception as e:
        print(f"❌ Gemini ranking failed: {e}")
        return _fallback_ranking(candidates)


# ── Step 3: Merge Gemini's ranking with our own candidate data ────────────────

def merge_rankings(candidates: list[dict], ranking_list: list[dict]) -> list[dict]:
    """Combine Gemini ranking fields with trusted candidate data (name, resume_url) by id."""
    candidates_by_id = {c.get("id"): c for c in candidates}
    merged = []
    for r in ranking_list:
        cid = r.get("id")
        candidate = candidates_by_id.get(cid)
        if candidate is None:
            continue
        merged.append({
            "id": cid,
            "name": candidate.get("name"),
            "rank": r.get("rank"),
            "why": r.get("why"),
            "fit": r.get("fit"),
            "concerns": r.get("concerns"),
            "experience": r.get("experience"),
            "resume_url": candidate.get("resume_file_url"),
        })
    merged.sort(key=lambda item: item.get("rank") if item.get("rank") is not None else 999)
    return merged


# ── Main search function ─────────────────────────────────────────────────────

def search(user_query: str, top_n: int = 3) -> dict:
    """Main entry point for candidate search."""
    print(f"\n{'═'*60}")
    print(f"🔎 Query: {user_query}")
    print(f"{'═'*60}")

    parsed_query = parse_query(user_query)
    print(f"\n📋 Parsed intent: {json.dumps(parsed_query, indent=2)}")

    candidates = search_candidates(parsed_query, top_n=top_n)

    if not candidates:
        return {
            "query": user_query,
            "parsed_intent": parsed_query,
            "total_found": 0,
            "results": [],
            "message": "No candidates matched your search criteria."
        }

    print(f"\n🤖 Ranking {len(candidates)} candidates with Gemini...")
    ranking_list = rank_with_gemini(candidates, user_query)
    merged_results = merge_rankings(candidates, ranking_list)

    return {
        "query": user_query,
        "parsed_intent": parsed_query,
        "total_found": len(candidates),
        "results": merged_results
    }


# ── test directly ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = search("Find me a Java developer")
    print(f"\n{'═'*60}")
    print("FINAL RESULTS:")
    print(f"{'═'*60}")
    print(json.dumps(result["results"], indent=2))