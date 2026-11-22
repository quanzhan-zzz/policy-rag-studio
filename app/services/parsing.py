from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


class UnsupportedDocumentError(ValueError):
    pass


SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".pdf", ".docx"}


def validate_document_type(file_name: str) -> None:
    if Path(file_name).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise UnsupportedDocumentError("仅支持 PDF、DOCX、TXT 和 Markdown 文件")


def parse_document(file_name: str, content: bytes) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return content.decode("gb18030", errors="replace")
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if suffix == ".docx":
        document = Document(BytesIO(content))
        paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n\n".join(paragraphs)
    raise UnsupportedDocumentError("仅支持 PDF、DOCX、TXT 和 Markdown 文件")
