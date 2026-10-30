"""Extract text from uploaded CVs. Content is treated as untrusted data."""
import io


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages).strip()
        if name.endswith(".docx"):
            import docx
            return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs).strip()
        if name.endswith((".txt", ".md")):
            return data.decode("utf-8", errors="replace").strip()
    except Exception as e:  # corrupt files must not crash the pipeline
        return f"[unreadable CV: {type(e).__name__}]"
    return ""
