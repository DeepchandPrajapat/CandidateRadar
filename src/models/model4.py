import os
import json
import re
from dotenv import load_dotenv
from datetime import datetime
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def call_ibm_model(text: str, parsed_json=None, mode="fields") -> dict:

    if not GEMINI_API_KEY:
        raise ValueError("❌ GEMINI_API_KEY is missing in .env file.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    

    # ---- Construct prompt (identical to your IBM version) ----
    if mode == "fields":
        today_str = datetime.today().strftime("%B %d, %Y")

        prompt = f"""Today's Date: {today_str}

You are an expert resume parser. Extract structured information from the given resume and return ONLY a valid JSON object.

COMPLETENESS REQUIREMENT: You MUST extract ALL information, not just the first few points. Read the ENTIRE resume text carefully and capture EVERY detail mentioned.

Use EXACTLY this JSON structure:
{{
    "Name": "string",
    "Contact Information": {{
        "Email": "string",
        "Phone": "string",
        "LinkedIn": "string"
    }},
    "Recent Employer": "string",
    "Total Experience": "string",
    "Professional Summary": "string",
    "Certifications": ["string1", "string2"],
    "Education": [
        {{
            "Qualification": "string",
            "Institution": "string",
            "Location": "string",
            "Start Year": "string",
            "End Year": "string",
            "CGPA/Percentage": "string"
        }}
    ],
    "Languages": ["string1", "string2"],
    "Employment History": [
        {{
            "Company Name": "string",
            "Job Title": "string",
            "Duration": "string",
            "Responsibilities": ["string1", "string2", "string3"]
        }}
    ],
    "Projects": [
        {{
            "Project Name": "string",
            "Role": "string",
            "Technologies Used": ["string1", "string2"],
            "Description": "string",
            "Duration": "string"
        }}
    ],
    "Hard Skills": ["string1", "string2", "string3"],
    "Soft Skills": ["string1", "string2"]
}}

CRITICAL JSON Rules:
- Return ONLY valid JSON — no markdown, no explanations, no extra text
- Use double quotes for ALL strings and property names
- NO trailing commas anywhere
- NO line breaks inside string values
- If a field is missing, use "Not mentioned" for strings or ["Not mentioned"] for arrays

Field Instructions:

Name: Extract full name as single string

Contact Information:
- Email: Extract email address
- Phone: Extract phone number with country code if present
- LinkedIn: Extract LinkedIn URL or profile name

Recent Employer: Name of most recent/current company

Total Experience:
- First check the professional summary. If experience explicitly mentioned (e.g., "4+ years", "5 years"), extract only that.
- If not found, calculate total from Employment History up to today's date.
- Format: "X years Y months"

Professional Summary:
- Complete summary of the candidate's experience, skills, and achievements.
- Do NOT use job titles as the summary.
- If not found, return "Not mentioned".

Certifications: Array of certification names

Education: Array of education objects
- If only graduation year mentioned, use it as End Year
- For ongoing education, add "(Pursuing)" to End Year

Languages: Only human languages (English, Hindi, etc.)
- Do NOT include programming languages

Employment History: EXTRACT ALL RESPONSIBILITIES
- Include ALL positions held
- List key responsibilities for each role

Projects:
- For Projects, always extract Duration if mentioned next to the project
- For Employment History, only assign responsibilities to a company if they are explicitly listed under that company, not from a shared section.
- Duration: Extract project duration if mentioned (e.g., "Jan 2018 - Sept 2023"), otherwise "Not mentioned"
- Include whole project description
- Read the ENTIRE project description
- If no role mentioned, use "Developer"

Hard Skills: Technical skills, tools, frameworks, programming languages

Soft Skills:
- Only behavioral/interpersonal strengths (leadership, teamwork, problem solving)
- Do NOT include technical practices or methodologies

Resume Text:
{text}"""

    else:
        prompt = f"""You are a JSON validation assistant. Compare the parsed JSON against the raw text and return a JSON report.

Raw Text:
{text}

Parsed JSON:
{json.dumps(parsed_json, indent=2)}

Return a validation report in this exact format:
{{
    "status": "valid" or "invalid",
    "mismatches": ["list of issues found"]
}}

Return ONLY valid JSON, no extra text."""

    # ---- Call Gemini ----
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
    )
        generated = response.text.strip()

        # Clean and parse 
        cleaned = clean_json_response(generated)

        try:
            parsed = json.loads(cleaned)
            return validate_and_fix_structure(parsed)

        except json.JSONDecodeError as e:
            print(f"❌ JSON decoding failed: {e}")
            print(f"Raw output: {generated}")
            print(f"Cleaned output: {cleaned}")
            return {"Error": "Gemini returned invalid JSON", "raw_output": cleaned}

    except Exception as e:
        print(f"❌ Error during resume extraction: {e}")
        return {"Error": str(e)}


def clean_json_response(response: str) -> str:

    if "```json" in response:
        response = response.split("```json")[1].split("```")[0]
    elif "```" in response:
        response = response.split("```")[1].split("```")[0]

    start_idx = response.find('{')
    if start_idx > 0:
        response = response[start_idx:]

    end_idx = response.rfind('}')
    if end_idx > 0:
        response = response[:end_idx + 1]

    response = response.replace('\n', ' ')
    response = response.replace('\r', ' ')
    response = re.sub(r'\s+', ' ', response)
    response = response.replace('\\u2014', '-')
    response = response.replace('\\"', '"')
    response = re.sub(r',\s*([}\]])', r'\1', response)

    return response.strip()


def validate_and_fix_structure(parsed_data: dict) -> dict:

    required_fields = {
        "Name": "Not mentioned",
        "Contact Information": {
            "Email": "Not mentioned",
            "Phone": "Not mentioned",
            "LinkedIn": "Not mentioned"
        },
        "Recent Employer": "Not mentioned",
        "Total Experience": "Not mentioned",
        "Professional Summary": "Not mentioned",
        "Certifications": ["Not mentioned"],
        "Education": [{
            "Qualification": "Not mentioned",
            "Institution": "Not mentioned",
            "Location": "Not mentioned",
            "Start Year": "Not mentioned",
            "End Year": "Not mentioned",
            "CGPA/Percentage": "Not mentioned"
        }],
        "Languages": ["Not mentioned"],
        "Employment History": [{
            "Company Name": "Not mentioned",
            "Job Title": "Not mentioned",
            "Duration": "Not mentioned",
            "Responsibilities": ["Not mentioned"]
        }],
        "Projects": [{
            "Project Name": "Not mentioned",
            "Role": "Not mentioned",
            "Technologies Used": ["Not mentioned"],
            "Description": "Not mentioned"
        }],
        "Hard Skills": ["Not mentioned"],
        "Soft Skills": ["Not mentioned"]
    }

    for field, default_value in required_fields.items():
        if field not in parsed_data:
            parsed_data[field] = default_value
        elif parsed_data[field] is None or parsed_data[field] == "":
            parsed_data[field] = default_value

    array_fields = ["Certifications", "Languages", "Hard Skills", "Soft Skills"]
    for field in array_fields:
        if isinstance(parsed_data.get(field), str):
            parsed_data[field] = [parsed_data[field]] if parsed_data[field] != "Not mentioned" else ["Not mentioned"]

    if not isinstance(parsed_data.get("Education"), list) or not parsed_data["Education"]:
        parsed_data["Education"] = [required_fields["Education"][0]]

    if not isinstance(parsed_data.get("Employment History"), list) or not parsed_data["Employment History"]:
        parsed_data["Employment History"] = [required_fields["Employment History"][0]]

    if not isinstance(parsed_data.get("Projects"), list) or not parsed_data["Projects"]:
        parsed_data["Projects"] = [required_fields["Projects"][0]]

    return parsed_data
