import json
from src.utils.pdf_utils import extract_text_from_pdf
from src.utils.docx_2_pdf_utils import convert_docx_to_pdf
from src.utils.ext_utils import get_file_extension
from src.models.model4 import call_ibm_model  # ✅ IBM model parser

def main(filename):
    ext = get_file_extension(filename).lower()

    if ext == ".pdf":
        text = extract_text_from_pdf(filename)

    elif ext == ".docx":
        # ✅ Convert DOCX to PDF
        print("📄 Converting DOCX to PDF...")
        pdf_file = convert_docx_to_pdf(filename)

        # ✅ Use pdfplumber on the converted PDF
        text = extract_text_from_pdf(pdf_file)

    else:
        print("❌ Unsupported file type!")
        return


    try:
        # ✅ Call IBM model
        parsed_json = call_ibm_model(text, mode="fields")

        # ❌ If the model returns an error, stop and show it
        if isinstance(parsed_json, dict) and "Error" in parsed_json:
            raise ValueError(f"IBM returned error: {parsed_json['Error']}")

        # ✅ Save valid output
        save_path = "D:/CandidateRadar/outputs2/abhi.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=4, ensure_ascii=False)

        print(f"✅ JSON saved successfully at: {save_path}")

    except Exception as e:
        print(f"❌ Error while parsing resume: {e}")

# --- Main Program Logic ---
if __name__ == "__main__":
    main(r"D:\CandidateRadar\inputs\resume\Abhishek Tyagi [4y_4m] - MERN Dev - Bangalore.pdf")
