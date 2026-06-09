import PyPDF2

def extract_text_from_pdf(filename):
    text = ""
    with open(filename, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text