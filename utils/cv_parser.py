"""
utils/cv_parser.py — Extract plain text from uploaded CV files (PDF or DOCX).
"""

import io
import streamlit as st


def extract_text_from_pdf(file) -> str:
    """Extract all text from a PDF file object using pdfplumber (fallback: pypdf)."""
    text_parts = []
    try:
        import pdfplumber
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception:
        pass  # fall through to pypdf

    # Fallback: pypdf
    try:
        from pypdf import PdfReader
        if hasattr(file, "read"):
            file.seek(0)
        reader = PdfReader(file)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Could not read PDF: {e}")


def extract_text_from_docx(file) -> str:
    """Extract all paragraph text from a DOCX file object."""
    try:
        from docx import Document
        doc = Document(file)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as e:
        raise ValueError(f"Could not read DOCX: {e}")


def extract_cv_text(uploaded_file) -> str:
    """
    Dispatch to correct parser based on file extension.
    Returns plain text string.
    Shows st.error and raises on failure.
    """
    if uploaded_file is None:
        st.error("No file uploaded.")
        raise ValueError("No file uploaded.")

    filename = uploaded_file.name.lower()
    file_bytes = io.BytesIO(uploaded_file.read())

    try:
        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(file_bytes)
        elif filename.endswith(".docx"):
            text = extract_text_from_docx(file_bytes)
        else:
            st.error("❌ Unsupported file type. Please upload a PDF or DOCX file.")
            raise ValueError("Unsupported file type.")
    except ValueError as ve:
        st.error(f"❌ Could not parse your CV: {ve}")
        raise

    if not text or len(text.strip()) < 50:
        st.warning("⚠️ Your CV appears to be empty or very short. Please upload a valid CV with your experience, skills, and projects.")
        raise ValueError("CV text too short or empty.")

    return text.strip()
