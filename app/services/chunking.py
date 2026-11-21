import re
from dataclasses import dataclass

from app.schemas import ChunkRecord, ChunkStrategy
from app.services.text import tokenize

HEADING_RE = re.compile(
    r"^(?:#{1,6}\s+.+|(?:[一二三四五六七八九十]+、).+|（[一二三四五六七八九十]+）.+)$"
)


def _is_heading_only(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return len(lines) == 1 and bool(HEADING_RE.match(lines[0]))


@dataclass(slots=True)
class ChunkDraft:
    text: str
    heading_path: str
    page: int = 1


def _make_chunks(
    document_id: str,
    document_title: str,
    strategy: ChunkStrategy,
    drafts: list[ChunkDraft],
) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    for index, draft in enumerate(drafts):
        text = draft.text.strip()
        if not text:
            continue
        chunks.append(
            ChunkRecord(
                id=f"{document_id}:{strategy.value}:{index}",
                document_id=document_id,
                document_title=document_title,
                strategy=strategy,
                page=draft.page,
                heading_path=draft.heading_path or "全文",
                text=text,
                tokens=len(tokenize(text)),
            )
        )
    return chunks


def fixed_chunks(
    text: str,
    document_id: str,
    document_title: str,
    chunk_size: int = 180,
    overlap: int = 36,
) -> list[ChunkRecord]:
    drafts: list[ChunkDraft] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(text), step):
        segment = text[start : start + chunk_size].strip()
        if segment:
            drafts.append(ChunkDraft(text=segment, heading_path="固定长度切片"))
        if start + chunk_size >= len(text):
            break
    return _make_chunks(document_id, document_title, ChunkStrategy.FIXED, drafts)


def heading_chunks(
    text: str,
    document_id: str,
    document_title: str,
) -> list[ChunkRecord]:
    drafts: list[ChunkDraft] = []
    current_heading = "全文"
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if (
            body
            and body not in {document_title, f"# {document_title}"}
            and not _is_heading_only(body)
        ):
            drafts.append(ChunkDraft(text=body, heading_path=current_heading))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if buffer and buffer[-1] != "":
                buffer.append("")
            continue
        if HEADING_RE.match(line):
            flush()
            buffer = [line]
            current_heading = line.removeprefix("#").strip()
        else:
            buffer.append(line)
    flush()

    if not drafts:
        return fixed_chunks(text, document_id, document_title)
    return _make_chunks(document_id, document_title, ChunkStrategy.HEADING, drafts)


def recursive_chunks(
    text: str,
    document_id: str,
    document_title: str,
    max_chars: int = 240,
) -> list[ChunkRecord]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    drafts: list[ChunkDraft] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            drafts.append(ChunkDraft(text="\n\n".join(current), heading_path="递归切片"))
            current.clear()

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            flush()
            for start in range(0, len(paragraph), max_chars):
                drafts.append(
                    ChunkDraft(text=paragraph[start : start + max_chars], heading_path="递归切片")
                )
            continue
        candidate = "\n\n".join([*current, paragraph])
        if current and len(candidate) > max_chars:
            flush()
        current.append(paragraph)
    flush()

    if not drafts:
        return fixed_chunks(text, document_id, document_title)
    return _make_chunks(document_id, document_title, ChunkStrategy.RECURSIVE, drafts)


def chunk_document(
    text: str,
    document_id: str,
    document_title: str,
    strategy: ChunkStrategy,
) -> list[ChunkRecord]:
    if strategy is ChunkStrategy.FIXED:
        return fixed_chunks(text, document_id, document_title)
    if strategy is ChunkStrategy.RECURSIVE:
        return recursive_chunks(text, document_id, document_title)
    return heading_chunks(text, document_id, document_title)
