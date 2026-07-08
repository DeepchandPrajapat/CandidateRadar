import os
import json
import psycopg2
from google import genai
from google.genai import types
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from src.rag.query_parser import parse_query
from src.rag.embedder import get_embedding_model

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client         = genai.Client(api_key=GEMINI_API_KEY)

DB_URL = os.getenv("SUPABASE_DB_URL")




def get_connection():
    return psycopg2.connect(DB_URL)


# ── Step 1: Single SQL query — filter + semantic search together ──────────────

def search_candidates(parsed_query: dict, top_n: int = 10) -> list[dict]:
    """
    One SQL query that filters by structured fields AND ranks by
    semantic similarity, using pgvector.
    """
    semantic_query = parsed_query.get("semantic_query", "")
    query_vector = get_embedding_model().encode(semantic_query).tolist()

    skills          = parsed_query.get("skills", [])
    min_experience  = parsed_query.get("min_experience", None)
    location        = parsed_query.get("location", None)
    recent_employer = parsed_query.get("recent_employer", None)

    conditions = []
    params     = {}

    if skills:
        conditions.append("skills && %(skills)s")
        params["skills"] = skills

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

    params["query_vector"] = str(query_vector)
    params["limit"]        = top_n

    sql = f"""
        SELECT
            id, name, email, phone, recent_employer,
            total_experience, experience_years, skills,
            resume_file_url, full_json,
            1 - (embedding <=> %(query_vector)s::vector) AS similarity
        FROM candidates
        {where_clause}
        ORDER BY embedding <=> %(query_vector)s::vector
        LIMIT %(limit)s
    """

    conn = get_connection()
    cur  = conn.cursor()

    try:
        cur.execute(sql, params)
        columns = [desc[0] for desc in cur.description]
        rows    = cur.fetchall()

        results = [dict(zip(columns, row)) for row in rows]

        print(f"\n🔍 Found {len(results)} candidates:")
        for r in results:
            print(f"   {r['name']} (similarity: {round(r['similarity'], 3)})")

        return results

    except Exception as e:
        print(f"❌ Search query failed: {e}")
        return []

    finally:
        cur.close()
        conn.close()


# ── Step 2: Rank with Gemini — returns structured JSON, not free text ─────────

def _strip_code_fences(text: str) -> str:
    """Gemini sometimes wraps JSON in ```json ... ``` even in JSON mode. Strip it defensively."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return cleaned.strip()


def _fallback_ranking(candidates: list[dict]) -> list[dict]:
    """Used only if Gemini call or JSON parsing fails — keeps the app working, no crash."""
    fallback = []
    rank_num = 1
    for c in candidates:
        fallback.append({
            "id"        : c.get("id"),
            "rank"      : rank_num,
            "why"       : "Automatic fallback ranking — ordered by semantic similarity because AI ranking was unavailable.",
            "fit"       : f"{c.get('total_experience') or 'Experience not specified'}, last at {c.get('recent_employer') or 'unknown employer'}.",
            "concerns"  : "Not evaluated — AI ranking failed for this search.",
            "experience": c.get("total_experience"),
        })
        rank_num += 1
    return fallback


def rank_with_gemini(candidates: list[dict], original_query: str) -> list[dict]:
    """
    Send filtered + semantically matched candidates to Gemini for ranking.
    Returns a list of dicts: [{id, rank, why, fit, concerns, experience}, ...]
    matched back to candidates by `id` — never by text position.
    """
    if not candidates:
        return []

    candidate_summaries = []

    for c in candidates:
        full_json = c.get("full_json", {})
        if isinstance(full_json, str):
            full_json = json.loads(full_json)

        # build employment list
        employment_list = []
        for job in full_json.get("Employment History", []):
            employment_list.append({
                "company" : job.get("Company Name"),
                "title"   : job.get("Job Title"),
                "duration": job.get("Duration"),
            })

        # build projects list with a normal for loop
        projects_list = []
        for p in full_json.get("Projects", []):
            if not isinstance(p, dict):
                continue
            projects_list.append({
                "name"    : p.get("Project Name"),
                "tech"    : p.get("Technologies Used", []),
                "duration": p.get("Duration", "Not mentioned"),
            })

        summary = {
            "id"              : c.get("id"),
            "name"            : c.get("name"),
            "total_experience": c.get("total_experience"),
            "recent_employer" : c.get("recent_employer"),
            "skills"          : c.get("skills", [])[:15],
            "summary"         : full_json.get("Professional Summary", "")[:300],
            "employment"      : employment_list,
            "projects"        : projects_list,
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
        print(f"❌ Gemini ranking failed or returned bad JSON: {e}")
        return _fallback_ranking(candidates)


# ── Step 3: Merge Gemini's ranking with our own trusted candidate data ───────

def merge_rankings(candidates: list[dict], ranking_list: list[dict]) -> list[dict]:
    """
    Combine Gemini's ranking fields (why/fit/concerns/experience/rank) with
    fields we trust from our own database row (name, resume_url) — matched by id.
    This way Gemini can never accidentally attach the wrong name or resume link.
    """
    candidates_by_id = {}
    for c in candidates:
        candidates_by_id[c.get("id")] = c

    merged = []
    for r in ranking_list:
        cid = r.get("id")
        candidate = candidates_by_id.get(cid)

        if candidate is None:
            # Gemini returned an id that doesn't match any real candidate — skip it
            continue

        merged.append({
            "id"        : cid,
            "name"      : candidate.get("name"),
            "rank"      : r.get("rank"),
            "why"       : r.get("why"),
            "fit"       : r.get("fit"),
            "concerns"  : r.get("concerns"),
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
            "query"        : user_query,
            "parsed_intent": parsed_query,
            "total_found"  : 0,
            "results"      : [],
            "message"      : "No candidates matched your search criteria."
        }

    print(f"\n🤖 Ranking {len(candidates)} candidates with Gemini...")
    ranking_list = rank_with_gemini(candidates, user_query)
    merged_results = merge_rankings(candidates, ranking_list)

    return {
        "query"        : user_query,
        "parsed_intent": parsed_query,
        "total_found"  : len(candidates),
        "results"      : merged_results
    }


# ── test directly ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = search("Find me a Java developer")
    print(f"\n{'═'*60}")
    print("FINAL RESULTS:")
    print(f"{'═'*60}")
    print(json.dumps(result["results"], indent=2))