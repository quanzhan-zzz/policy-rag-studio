from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

import httpx
from pypdf import PdfReader

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
ATTACHMENT_PATTERN = re.compile(r"downloadClyb\('([^']+)'")
CONTENT_DISPOSITION_FILENAME = re.compile(
    r"filename\*?=(?:UTF-8''|[\"']?)([^\"';]+)",
    flags=re.IGNORECASE,
)
SECTION_LABELS = {
    "floor1": "基本信息",
    "floor2": "部门信息",
    "floor3": "窗口办理",
    "floor4": "受理标准",
    "floor10": "办理材料",
    "floor5": "办理流程",
    "floor6": "办理时限",
    "floor7": "收费情况",
    "floor8": "审批结果",
    "floor11": "法律依据",
    "floor12": "常见问题",
    "floor13": "咨询投诉",
    "floor14": "权利义务",
    "floor15": "法律救济",
}
SECTION_ORDER = tuple(SECTION_LABELS)
ALLOWED_ATTACHMENT_SUFFIXES = {
    ".doc",
    ".docx",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".txt",
    ".xls",
    ".xlsx",
    ".zip",
}
PUBLIC_SERVICE_PATH = "/jszwfw/publicservice/itemlist/showDetail.do"
ADMIN_SERVICE_PATH = "/jszwfw/bscx/itemlist/bszn.do"
GUIDE_DOWNLOAD_PATH = "/jszwfw/bscx/item/gzxxgztb_download.do"


class OfficialSourceError(RuntimeError):
    """Raised when an official source cannot be fetched or normalized."""


@dataclass(frozen=True, slots=True)
class GuideSource:
    id: str
    title: str
    ql_kind: str
    yw_code: str
    ql_code: str
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceCatalog:
    source_name: str
    source_base_url: str
    list_url: str
    web_id: str
    guides: tuple[GuideSource, ...]


@dataclass(frozen=True, slots=True)
class ParsedGuide:
    title: str
    department: str
    text: str
    sections: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class ImportSummary:
    output_path: Path
    manifest_path: Path
    guide_count: int
    attachment_count: int
    guide_hashes: dict[str, str]


class _GuideHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.sections: dict[str, list[str]] = {}
        self._in_title = False
        self._section_id: str | None = None
        self._section_div_depth = 0
        self._hidden_div_depth = 0
        self._skip_text_depth = 0
        self._line_parts: list[str] = []
        self._row_cells: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        if tag == "div" and attributes.get("id") in SECTION_LABELS:
            if self._section_id is not None:
                self._flush_line()
            self._section_id = attributes["id"]
            self._section_div_depth = 1
            self._hidden_div_depth = 0
            self._skip_text_depth = 0
            self._line_parts.clear()
            self._row_cells = None
            self._cell_parts = None
            self.sections.setdefault(self._section_id, [])
            return

        if self._section_id is None:
            return

        if tag in {"script", "style", "noscript"}:
            self._skip_text_depth += 1
            return
        if tag == "div":
            self._section_div_depth += 1
            if self._hidden_div_depth:
                self._hidden_div_depth += 1
                return
            if "bszn_clxq" in attributes.get("class", "").split():
                self._hidden_div_depth = 1
                return
        if self._hidden_div_depth or self._skip_text_depth:
            return
        if tag == "tr":
            self._row_cells = []
        elif tag in {"td", "th"}:
            self._cell_parts = []
        elif tag == "br":
            self._flush_line()
        elif tag in {"p", "li"}:
            self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            return
        if self._section_id is None:
            return
        if tag in {"script", "style", "noscript"}:
            self._skip_text_depth = max(0, self._skip_text_depth - 1)
            return
        if self._hidden_div_depth:
            if tag == "div":
                self._hidden_div_depth -= 1
                self._section_div_depth = max(0, self._section_div_depth - 1)
            return
        if self._skip_text_depth:
            return
        if tag in {"td", "th"}:
            if self._cell_parts is not None and self._row_cells is not None:
                cell = self._join_parts(self._cell_parts)
                if cell:
                    self._row_cells.append(cell)
            self._cell_parts = None
        elif tag == "tr":
            if self._row_cells:
                self._append_line(" | ".join(self._row_cells))
            self._row_cells = None
        elif tag in {"p", "li"}:
            self._flush_line()
        elif tag == "div":
            if self._section_div_depth == 1:
                self._flush_line()
                self._section_id = None
                self._section_div_depth = 0
                self._row_cells = None
                self._cell_parts = None
            else:
                self._section_div_depth -= 1
                self._flush_line()

    def handle_data(self, data: str) -> None:
        normalized = self._join_parts([data])
        if not normalized:
            return
        if self._in_title:
            self.title_parts.append(normalized)
            return
        if self._section_id is None:
            return
        if self._hidden_div_depth or self._skip_text_depth:
            return
        if self._cell_parts is not None:
            self._cell_parts.append(normalized)
        else:
            self._line_parts.append(normalized)

    def close(self) -> None:
        super().close()
        self._flush_line()

    def _flush_line(self) -> None:
        line = self._join_parts(self._line_parts)
        self._line_parts.clear()
        if line:
            self._append_line(line)

    def _append_line(self, line: str) -> None:
        if self._section_id is None:
            return
        section = self.sections[self._section_id]
        label = SECTION_LABELS[self._section_id]
        if line == label:
            return
        if line.startswith(f"{label} "):
            line = line[len(label) :].strip()
        for suffix in ("查看简版指南 >", "点击查看办理流程图 >"):
            if line.endswith(suffix):
                line = line[: -len(suffix)].strip()
        if line and (not section or section[-1] != line):
            section.append(line)

    @staticmethod
    def _join_parts(parts: Iterable[str]) -> str:
        return " ".join(" ".join(parts).split()).strip()


@dataclass(frozen=True, slots=True)
class _DownloadedFile:
    content: bytes
    content_type: str
    remote_name: str | None


def load_source_catalog(path: Path) -> SourceCatalog:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        guides = tuple(
            GuideSource(
                id=str(item["id"]),
                title=str(item["title"]),
                ql_kind=str(item["ql_kind"]),
                yw_code=str(item["yw_code"]),
                ql_code=str(item["ql_code"]),
                tags=tuple(str(tag) for tag in item.get("tags", [])),
            )
            for item in payload["guides"]
        )
        catalog = SourceCatalog(
            source_name=str(payload["source_name"]),
            source_base_url=str(payload["source_base_url"]).rstrip("/"),
            list_url=str(payload["list_url"]),
            web_id=str(payload["web_id"]),
            guides=guides,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise OfficialSourceError(f"来源目录格式无效：{path}") from error
    if not catalog.guides:
        raise ValueError("来源目录至少需要一个事项")
    identifiers = [guide.id for guide in catalog.guides]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("来源目录包含重复事项 ID")
    return catalog


def detail_url(source_base_url: str, guide: GuideSource) -> str:
    path = PUBLIC_SERVICE_PATH if guide.ql_kind == "20" else ADMIN_SERVICE_PATH
    return f"{source_base_url}{path}"


def detail_params(web_id: str, guide: GuideSource) -> dict[str, str]:
    return {
        "webId": web_id,
        "iddept_yw_inf": guide.yw_code,
        "ql_kind": guide.ql_kind,
        "iddept_ql_inf": guide.ql_code,
    }


def download_params(web_id: str, guide: GuideSource) -> dict[str, str]:
    return {
        "webId": web_id,
        "iddeptYwInf": guide.yw_code,
        "qlKind": guide.ql_kind,
        "iddeptQlInf": guide.ql_code,
        "guideType": "1",
    }


def parse_guide_html(content: str, fallback_title: str) -> ParsedGuide:
    parser = _GuideHTMLParser()
    parser.feed(content)
    parser.close()
    title = " ".join(parser.title_parts).strip() or fallback_title
    if title != fallback_title:
        raise OfficialSourceError(f"指南标题不匹配：期望 {fallback_title}，实际 {title}")
    sections = {
        SECTION_LABELS[section_id]: tuple(lines)
        for section_id, lines in parser.sections.items()
        if lines
    }
    titled_sections = [
        f"## {label}\n" + "\n".join(sections[label])
        for section_id in SECTION_ORDER
        if (label := SECTION_LABELS[section_id]) in sections
    ]
    if not titled_sections:
        raise OfficialSourceError(f"指南正文为空：{title}")
    department = _extract_department(sections)
    text = f"# {title}\n\n" + "\n\n".join(titled_sections) + "\n"
    return ParsedGuide(
        title=title,
        department=department,
        text=text,
        sections=sections,
    )


def extract_attachment_urls(content: str) -> tuple[str, ...]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in ATTACHMENT_PATTERN.finditer(content):
        url = html.unescape(match.group(1)).strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return tuple(urls)


def filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    match = CONTENT_DISPOSITION_FILENAME.search(value)
    if match is None:
        return None
    return Path(unquote(match.group(1).strip())).name or None


def import_official_guides(
    catalog_path: Path,
    *,
    output_path: Path,
    manifest_path: Path,
    raw_dir: Path,
    client: httpx.Client | None = None,
    generated_at: datetime | None = None,
) -> ImportSummary:
    catalog = load_source_catalog(catalog_path)
    generated_at = generated_at or datetime.now(UTC)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    owns_client = client is None
    http_client = client or httpx.Client(
        follow_redirects=True,
        timeout=45.0,
        headers={"User-Agent": "PolicyRAG-Studio/0.2 official-source-import"},
    )
    try:
        records: list[dict[str, object]] = []
        manifest_guides: list[dict[str, object]] = []
        guide_hashes: dict[str, str] = {}
        attachment_count = 0
        for guide in catalog.guides:
            record, manifest_entry = _import_one_guide(
                http_client,
                catalog,
                guide,
                raw_dir=raw_dir,
                generated_at=generated_at,
            )
            records.append(record)
            manifest_guides.append(manifest_entry)
            guide_hashes[guide.id] = str(record["source_pdf_sha256"])
            attachment_count += len(record["attachments"])
    except httpx.HTTPError as error:
        raise OfficialSourceError(f"官方来源请求失败：{error}") from error
    finally:
        if owns_client:
            http_client.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl = "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
    manifest = {
        "schema_version": 1,
        "source_name": catalog.source_name,
        "list_url": catalog.list_url,
        "generated_at": _isoformat(generated_at),
        "guides": manifest_guides,
    }
    _write_text_atomic(output_path, jsonl)
    _write_text_atomic(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    return ImportSummary(
        output_path=output_path,
        manifest_path=manifest_path,
        guide_count=len(records),
        attachment_count=attachment_count,
        guide_hashes=guide_hashes,
    )


def _import_one_guide(
    client: httpx.Client,
    catalog: SourceCatalog,
    guide: GuideSource,
    *,
    raw_dir: Path,
    generated_at: datetime,
) -> tuple[dict[str, object], dict[str, object]]:
    detail_response = client.get(
        detail_url(catalog.source_base_url, guide),
        params=detail_params(catalog.web_id, guide),
    )
    _raise_for_status(detail_response, f"指南详情 {guide.title}")
    parsed = parse_guide_html(detail_response.text, guide.title)
    pdf = _download_file(
        client,
        f"{catalog.source_base_url}{GUIDE_DOWNLOAD_PATH}",
        params=download_params(catalog.web_id, guide),
        label=f"指南 PDF {guide.title}",
    )
    _validate_pdf(pdf.content, guide.title)

    guide_raw_dir = raw_dir / guide.id
    pdf_path = guide_raw_dir / "guide.pdf"
    _write_bytes(pdf_path, pdf.content)
    pdf_hash = _sha256(pdf.content)

    attachment_records: list[dict[str, object]] = []
    used_attachment_names: set[str] = set()
    for index, url in enumerate(extract_attachment_urls(detail_response.text), start=1):
        attachment = _download_file(client, url, label=f"材料附件 {guide.title}")
        remote_name = attachment.remote_name or _fallback_attachment_name(
            attachment.content_type,
            index=index,
        )
        safe_name = _unique_attachment_name(
            _safe_attachment_name(remote_name),
            used_attachment_names,
        )
        used_attachment_names.add(safe_name)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in ALLOWED_ATTACHMENT_SUFFIXES:
            raise OfficialSourceError(
                f"不支持的附件类型：{safe_name} ({attachment.content_type})"
            )
        attachment_path = guide_raw_dir / "attachments" / safe_name
        _write_bytes(attachment_path, attachment.content)
        relative_path = attachment_path.relative_to(raw_dir).as_posix()
        attachment_records.append(
            {
                "name": safe_name,
                "url": url,
                "content_type": attachment.content_type,
                "path": relative_path,
                "sha256": _sha256(attachment.content),
                "size_bytes": len(attachment.content),
            }
        )

    text_hash = _sha256(parsed.text.encode("utf-8"))
    record: dict[str, object] = {
        "id": guide.id,
        "title": parsed.title,
        "department": parsed.department,
        "tags": ["官方", catalog.source_name, *guide.tags],
        "source_name": catalog.source_name,
        "source_url": str(detail_response.url),
        "source_list_url": catalog.list_url,
        "source_retrieved_at": _isoformat(generated_at),
        "source_pdf_path": f"{guide.id}/guide.pdf",
        "source_pdf_sha256": pdf_hash,
        "text_sha256": text_hash,
        "text": parsed.text,
        "attachments": attachment_records,
    }
    manifest_entry: dict[str, object] = {
        "id": guide.id,
        "title": parsed.title,
        "source_url": str(detail_response.url),
        "source_pdf": {
            "remote_name": pdf.remote_name,
            "content_type": pdf.content_type,
            "path": f"{guide.id}/guide.pdf",
            "sha256": pdf_hash,
            "size_bytes": len(pdf.content),
        },
        "attachments": attachment_records,
    }
    return record, manifest_entry


def _download_file(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, str] | None = None,
    label: str,
) -> _DownloadedFile:
    response = client.get(url, params=params)
    _raise_for_status(response, label)
    content = response.content
    if not content:
        raise OfficialSourceError(f"{label} 返回空文件")
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise OfficialSourceError(f"{label} 超过 {MAX_DOWNLOAD_BYTES} 字节限制")
    content_type = response.headers.get("content-type", "application/octet-stream")
    remote_name = filename_from_content_disposition(
        response.headers.get("content-disposition")
    )
    return _DownloadedFile(
        content=content,
        content_type=content_type.split(";", 1)[0].strip().lower(),
        remote_name=remote_name,
    )


def _raise_for_status(response: httpx.Response, label: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise OfficialSourceError(
            f"{label} 返回 HTTP {response.status_code}"
        ) from error


def _validate_pdf(content: bytes, title: str) -> None:
    if not content.startswith(b"%PDF-"):
        raise OfficialSourceError(f"指南下载结果不是 PDF：{title}")
    try:
        reader = PdfReader(BytesIO(content))
        page_count = len(reader.pages)
    except Exception as error:
        raise OfficialSourceError(f"指南 PDF 无法解析：{title}") from error
    if page_count == 0:
        raise OfficialSourceError(f"指南 PDF 没有页面：{title}")


def _extract_department(sections: dict[str, tuple[str, ...]]) -> str:
    text = "\n".join(sections.get("部门信息", ()))
    match = re.search(r"实施主体\s*\|\s*([^|]+)", text)
    if match:
        return match.group(1).strip()
    return "未提取"


def _fallback_attachment_name(content_type: str, *, index: int) -> str:
    suffix = mimetypes.guess_extension(content_type) or ".bin"
    return f"attachment-{index}{suffix}"


def _safe_attachment_name(name: str) -> str:
    basename = Path(name.replace("\\", "/")).name.strip()
    cleaned = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", basename)
    return cleaned or "attachment.bin"


def _unique_attachment_name(name: str, used_names: set[str]) -> str:
    if name not in used_names:
        return name
    path = Path(name)
    index = 2
    while True:
        candidate = f"{path.stem}-{index}{path.suffix}"
        if candidate not in used_names:
            return candidate
        index += 1


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
