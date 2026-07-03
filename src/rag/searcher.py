import os
import json
import psycopg2
from google import genai
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from query_parser import parse_query

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client         = genai.Client(api_key=GEMINI_API_KEY)

DB_URL = os.getenv("SUPABASE_DB_URL")

print("⏳ Loading embedding model...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Embedding model loaded")


def get_connection():
    return psycopg2.connect(DB_URL)


# ── Step 1: Single SQL query — filter + semantic search together ──────────────

def search_candidates(parsed_query: dict, top_n: int = 10) -> list[dict]:
    """
    One SQL query that filters by structured fields AND ranks by
    semantic similarity, using pgvector.
    """
    semantic_query = parsed_query.get("semantic_query", "")
    query_vector   = embedding_model.encode(semantic_query).tolist()

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

    params["query_vector"] = query_vector
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


# ── Step 2: Rank with Gemini ────────────────────────────────────────────────────

def rank_with_gemini(candidates: list[dict], original_query: str) -> str:
    """Send filtered + semantically matched candidates to Gemini for ranking."""
    if not candidates:
        return "No candidates matched your search criteria."

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

Rank ALL candidates from best to worst fit. For each candidate provide:
1. Rank number
2. Name
3. Why they are a good fit (be specific — mention relevant skills, experience, projects)
4. Any concerns or gaps
5. Estimated years of experience in the specific skills mentioned in the requirement

Return your response in this format for each candidate:

Rank #X — [Name]
Fit: [specific reasons why they match]
Concerns: [any gaps or mismatches]
Skill-specific experience: [estimate based on their employment history]
---
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()

    except Exception as e:
        print(f"❌ Gemini ranking failed: {e}")
        fallback_lines = []
        for c in candidates:
            line = f"{c.get('name')} — {c.get('total_experience')} — {c.get('recent_employer')}"
            fallback_lines.append(line)
        return "\n".join(fallback_lines)


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
            "query"  : user_query,
            "results": [],
            "ranking": "No candidates matched your search criteria."
        }

    print(f"\n🤖 Ranking {len(candidates)} candidates with Gemini...")
    ranking = rank_with_gemini(candidates, user_query)

    result_ids = []
    for c in candidates:
        result_ids.append(c.get("id"))

    return {
        "query"        : user_query,
        "parsed_intent": parsed_query,
        "total_found"  : len(candidates),
        "results"      : result_ids,
        "ranking"      : ranking
    }


# ── test directly ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = search("Find me a Java developer")
    print(f"\n{'═'*60}")
    print("FINAL RANKING:")
    print(f"{'═'*60}")
    print(result["ranking"])