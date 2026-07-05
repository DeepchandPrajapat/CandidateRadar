import os
import subprocess
import sys

def convert_docx_to_pdf(docx_path):
    """Convert DOCX to PDF without requiring Microsoft Word."""
    pdf_path = docx_path.replace(".docx", ".converted.pdf")
    output_dir = os.path.dirname(docx_path) or "."

    try:
        # Method 1: LibreOffice headless (works on Linux/Render, no Word needed)
        result = subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                docx_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

        # LibreOffice names the output <original_name>.pdf
        original_pdf_path = os.path.join(
            output_dir,
            os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
        )

        if os.path.exists(original_pdf_path):
            if os.path.exists(pdf_path):
                os.remove(pdf_path)  # remove old .converted.pdf if exists
            os.rename(original_pdf_path, pdf_path)
            print(f"✅ Converted using LibreOffice: {pdf_path}")
            return pdf_path
        else:
            raise RuntimeError("LibreOffice did not produce expected output file")

    except Exception as e:
        print(f"⚠️ LibreOffice conversion failed: {e}, trying fallback...")

    try:
        # Method 2: python-docx + reportlab (plain text only, no formatting —
        # last resort if LibreOffice is unavailable or fails)
        from docx import Document
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        doc = Document(docx_path)
        pdf_doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        for para in doc.paragraphs:
            if para.text.strip():
                story.append(Paragraph(para.text, styles['Normal']))
                story.append(Spacer(1, 6))

        pdf_doc.build(story)
        print(f"✅ Converted using fallback method: {pdf_path}")
        return pdf_path

    except Exception as e:
        print(f"❌ All conversion methods failed: {e}")
        raise