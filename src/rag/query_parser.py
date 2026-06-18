import os
import json
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


def parse_query(user_query: str) -> dict:
    """
    Takes a natural language recruiter query and returns structured intent."""


    prompt = f"""You are a recruiter search assistant. Analyze this job search query and extract structured information.

Query: "{user_query}"

Return a JSON object with ONLY the fields that are clearly mentioned or implied in the query.
Do NOT include fields that are not mentioned. Do NOT return null values.

Possible fields you can return:
- "skills": array of specific technologies, programming languages, or tools mentioned
- "min_experience": minimum years of experience as a number (e.g. 5, 3.5)
- "location": city or region if mentioned
- "recent_employer": specific company name if mentioned
- "semantic_query": a clean, enriched version of the query focused on domain, role, and experience context — this is used for semantic search so make it descriptive and meaningful

Rules:
- "semantic_query" should always be included — it captures the overall meaning
- For min_experience: "5+ years" → 5, "3 to 5 years" → 3, "senior" → 5, "junior" → 1
- For skills: only extract explicit technologies, not vague terms like "good communication"
- Return ONLY valid JSON, no markdown, no explanation

Examples:

Query: "ReactJS developer with 5+ years who worked on fintech projects"
Output:
{{
    "skills": ["ReactJS"],
    "min_experience": 5,
    "semantic_query": "ReactJS frontend developer fintech projects experience"
}}

Query: "Find me a Java developer in Bangalore"
Output:
{{
    "skills": ["Java"],
    "location": "Bangalore",
    "semantic_query": "Java backend developer Bangalore"
}}

Query: "Someone with microservices and system design experience"
Output:
{{
    "semantic_query": "microservices architecture system design experience backend"
}}

Query: "Senior Python developer who worked at a product company"
Output:
{{
    "skills": ["Python"],
    "min_experience": 5,
    "semantic_query": "senior Python developer product company experience"
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = response.text.strip()

        # clean markdown if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        parsed = json.loads(raw.strip())
        return parsed

    except json.JSONDecodeError as e:
        print(f"❌ Gemini returned invalid JSON: {e}")
        print(f"Raw output: {raw}")
        # fallback — treat whole query as semantic search
        return {"semantic_query": user_query}

    except Exception as e:
        print(f"❌ Query parsing failed: {e}")
        return {"semantic_query": user_query}


# ── test directly ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_queries = [
        "ReactJS developer with 5+ years who worked on fintech projects",
        "Find me a Java developer in Bangalore",
        "Someone with microservices and system design experience",
        "Senior Python developer who worked at Infosys",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        result = parse_query(query)
        print(f"Parsed: {json.dumps(result, indent=2)}")
        print("─" * 50)