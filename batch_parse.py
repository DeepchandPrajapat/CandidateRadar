import os
import json
import time
from src.utils.pdf_utils import extract_text_from_pdf
from src.utils.docx_2_pdf_utils import convert_docx_to_pdf
from src.utils.ext_utils import get_file_extension
from src.models.model4 import call_ibm_model

RESUME_FOLDER = r"D:\CandidateRadar\inputs\resume2"
OUTPUT_FOLDER = r"D:\CandidateRadar\outputs2"


def parse_one_resume(filepath: str) -> dict | None:
    """Extract text and call Gemini to parse a single resume file."""
    ext = get_file_extension(filepath).lower()

    if ext == ".pdf":
        text = extract_text_from_pdf(filepath)

    elif ext == ".docx":
        print("📄 Converting DOCX to PDF...")
        pdf_file = convert_docx_to_pdf(filepath)
        text = extract_text_from_pdf(pdf_file)

    else:
        print(f"❌ Unsupported file type: {filepath}")
        return None

    try:
        parsed_json = call_ibm_model(text, mode="fields")

        if isinstance(parsed_json, dict) and "Error" in parsed_json:
            raise ValueError(f"Model returned error: {parsed_json['Error']}")

        return parsed_json

    except Exception as e:
        print(f"❌ Error while parsing resume: {e}")
        return None


def get_output_filename(input_filepath: str) -> str:
    """
    Build a clean output filename from the input file.
    e.g. 'Naukri_AbhishekBarolia[5y_0m].pdf' -> 'Naukri_AbhishekBarolia5y_0m.json'
    """
    base_name = os.path.splitext(os.path.basename(input_filepath))[0]

    # remove characters that are unsafe for filenames
    for bad_char in ["[", "]", "(", ")"]:
        base_name = base_name.replace(bad_char, "")

    # collapse extra spaces
    base_name = " ".join(base_name.split())
    base_name = base_name.replace(" ", "_")

    return base_name + ".json"


def batch_parse_all_resumes() -> None:
    """
    Loop through every resume in RESUME_FOLDER, parse each one,
    and save the result as a JSON file in OUTPUT_FOLDER.
    Skips files that are already parsed (output JSON already exists).
    """
    if not os.path.exists(RESUME_FOLDER):
        print(f"❌ Resume folder not found: {RESUME_FOLDER}")
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    all_files = os.listdir(RESUME_FOLDER)
    resume_files = []

    for filename in all_files:
        ext = get_file_extension(filename).lower()
        if ext in [".pdf", ".docx"]:
            resume_files.append(filename)

    print(f"\n📂 Found {len(resume_files)} resumes in {RESUME_FOLDER}\n")

    parsed_count  = 0
    skipped_count = 0
    failed_count  = 0

    for index, filename in enumerate(resume_files, start=1):
        filepath        = os.path.join(RESUME_FOLDER, filename)
        output_filename = get_output_filename(filename)
        output_path     = os.path.join(OUTPUT_FOLDER, output_filename)

        print(f"[{index}/{len(resume_files)}] Processing: {filename}")

        # skip if already parsed
        if os.path.exists(output_path):
            print(f"   ⏭️  Already parsed, skipping.")
            skipped_count += 1
            continue

        parsed_json = parse_one_resume(filepath)

        if parsed_json is None:
            print(f"   ❌ Failed to parse: {filename}")
            failed_count += 1
            continue

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=4, ensure_ascii=False)

        print(f"   ✅ Saved: {output_filename}")
        parsed_count += 1

        # small delay to respect Gemini free tier rate limits
        time.sleep(2)

    print(f"\n{'─'*50}")
    print(f"✅ Parsed  : {parsed_count}")
    print(f"⏭️  Skipped : {skipped_count}")
    print(f"❌ Failed  : {failed_count}")


if __name__ == "__main__":
    batch_parse_all_resumes()