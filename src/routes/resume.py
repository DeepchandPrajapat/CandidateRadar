import os
import hashlib
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException,Depends,Header
from typing import List
from supabase import create_client
from dotenv import load_dotenv
from src.utils.pdf_utils import extract_text_from_pdf
from src.utils.docx_2_pdf_utils import convert_docx_to_pdf
from src.utils.ext_utils import get_file_extension
from src.models.model4 import call_ibm_model
from src.rag.embedder import index_single_resume

load_dotenv()

SUPABASE_URL    = os.getenv("SUPABASE_URL")
SUPABASE_KEY    = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("API_KEY")
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

MAX_UPLOAD_LIMIT = 5

router = APIRouter()


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def compute_hash(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


def upload_to_storage(file_bytes: bytes, filename: str) -> str:
    """Upload original resume file to Supabase Storage, return public URL."""
    path = f"resumes/{filename}"

    supabase_client.storage.from_("resumes").upload(
        path=path,
        file=file_bytes,
        file_options={"content-type": "application/octet-stream", "upsert": "true"}
    )

    url_response = supabase_client.storage.from_("resumes").get_public_url(path)
    return url_response


def parse_resume_text(file_bytes: bytes, filename: str) -> str:
    """Save file temporarily, extract text, return raw text."""
    ext = get_file_extension(filename).lower()

    # write bytes to a temp file so existing utils can read it
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        if ext == ".pdf":
            text = extract_text_from_pdf(tmp_path)

        elif ext == ".docx":
            pdf_path = convert_docx_to_pdf(tmp_path)
            text     = extract_text_from_pdf(pdf_path)
            os.remove(pdf_path)

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    finally:
        os.remove(tmp_path)

    return text


@router.post("/upload")
async def upload_resumes(files: List[UploadFile] = File(...),api_key: str = Depends(verify_api_key)):
    
    """
    Upload up to 5 resume files (PDF or DOCX).
    Each file is:
      1. Uploaded to Supabase Storage
      2. Parsed by Gemini into structured JSON
      3. Embedded and indexed into Supabase candidates table
    """
    if len(files) > MAX_UPLOAD_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Max {MAX_UPLOAD_LIMIT} files per upload. You sent {len(files)}."
        )

    uploaded = 0
    skipped  = 0
    failed   = 0
    results  = []

    for file in files:
        filename  = file.filename
        file_bytes = await file.read()
        file_hash  = compute_hash(file_bytes)

        try:
            # step 1 — upload original file to Supabase Storage
            resume_file_url = upload_to_storage(file_bytes, filename)

            # step 2 — extract text
            text = parse_resume_text(file_bytes, filename)

            # step 3 — parse with Gemini
            parsed_json = call_ibm_model(text, mode="fields")

            if isinstance(parsed_json, dict) and "Error" in parsed_json:
                raise ValueError(f"Gemini error: {parsed_json['Error']}")

            # step 4 — embed + insert into Supabase candidates table
            new_id = index_single_resume(
                resume=parsed_json,
                file_hash=file_hash,
                resume_file_url=resume_file_url
            )

            if new_id is None:
                skipped += 1
                results.append({"file": filename, "status": "duplicate"})
            else:
                uploaded += 1
                results.append({"file": filename, "status": "success", "id": new_id})

        except HTTPException:
            raise

        except Exception as e:
            failed += 1
            results.append({"file": filename, "status": "failed", "error": str(e)})

    return {
        "uploaded": uploaded,
        "skipped" : skipped,
        "failed"  : failed,
        "details" : results
    }