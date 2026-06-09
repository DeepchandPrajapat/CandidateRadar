import os
import subprocess
import sys

def convert_docx_to_pdf(docx_path):
    """Convert DOCX to PDF without requiring Microsoft Word."""
    pdf_path = docx_path.replace(".docx", ".converted.pdf")
    
    try:
        # Method 1: try docx2pdf (works if Word is not busy)
        from docx2pdf import convert as docx_to_pdf
        docx_to_pdf(docx_path, os.path.dirname(docx_path))
        original_pdf_path = docx_path.replace(".docx", ".pdf")
        if os.path.exists(original_pdf_path):
            if os.path.exists(pdf_path):
                os.remove(pdf_path)  # remove old .converted.pdf if exists
            os.rename(original_pdf_path, pdf_path)
            return pdf_path
            
    except Exception as e:
        print(f"⚠️ docx2pdf failed: {e}, trying fallback...")

    try:
        # Method 2: python-docx + reportlab (no Word needed)
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