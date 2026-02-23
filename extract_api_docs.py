import sys
import os

pdf_path = "d:/OneDrive/Data/Fairline/Illumio/RD/illumio_monitor/docs/REST_APIs_25_2.pdf"
out_path = "d:/OneDrive/Data/Fairline/Illumio/RD/illumio_monitor/docs/extracted_api_docs.txt"

# Keywords to search
keywords = [
    "/events", 
    "/traffic_flows/async_queries", 
    "async_queries", 
    "/health",
    "traffic_flows"
]

def extract_pdf():
    try:
        from pypdf import PdfReader
        print("Using pypdf")
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        print(f"Total pages: {total_pages}")
        
        relevant_pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text_lower = text.lower()
            if any(k in text_lower for k in keywords):
                relevant_pages.append((i+1, text))
                
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"Total extracted pages: {len(relevant_pages)}\n\n")
            for page_num, text in relevant_pages:
                f.write(f"--- Page {page_num} ---\n{text}\n\n")
        print(f"Extracted {len(relevant_pages)} pages to {out_path}")
    except ImportError:
        print("pypdf not found. Trying fitz (PyMuPDF)")
        import fitz
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        print(f"Total pages: {total_pages}")
        
        relevant_pages = []
        for i in range(total_pages):
            page = doc.load_page(i)
            text = page.get_text()
            text_lower = text.lower()
            if any(k in text_lower for k in keywords):
                relevant_pages.append((i+1, text))
                
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"Total extracted pages: {len(relevant_pages)}\n\n")
            for page_num, text in relevant_pages:
                f.write(f"--- Page {page_num} ---\n{text}\n\n")
        print(f"Extracted {len(relevant_pages)} pages to {out_path}")

if __name__ == "__main__":
    extract_pdf()
