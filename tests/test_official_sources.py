import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.services.official_sources import (
    OfficialSourceError,
    extract_attachment_urls,
    filename_from_content_disposition,
    import_official_guides,
    load_source_catalog,
    parse_guide_html,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "jszwfw"
GUIDE_TITLE = "公司变更登记注册（设区的市级权限）"


def test_checked_in_catalog_is_valid() -> None:
    catalog = load_source_catalog(ROOT / "data/sources/jszwfw/catalog.json")

    assert catalog.source_name == "江苏政务服务网·常州法人服务"
    assert {guide.id for guide in catalog.guides} == {
        "cz-company-change-registration",
        "cz-public-welfare-post-subsidy",
    }


def test_checked_in_corpus_matches_manifest_hashes() -> None:
    manifest_path = ROOT / "data/official/jszwfw-guides.v1.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = {
        record["id"]: record
        for record in (
            json.loads(line)
            for line in (
                ROOT / "data/official/jszwfw-guides.v1.jsonl"
            ).read_text(encoding="utf-8").splitlines()
        )
    }
    raw_root = manifest_path.parent / "raw" / "jszwfw"

    assert records.keys() == {guide["id"] for guide in manifest["guides"]}
    for guide in manifest["guides"]:
        record = records[guide["id"]]
        pdf_path = raw_root / guide["source_pdf"]["path"]
        assert _sha256(pdf_path.read_bytes()) == record["source_pdf_sha256"]
        for attachment in guide["attachments"]:
            attachment_path = raw_root / attachment["path"]
            assert _sha256(attachment_path.read_bytes()) == attachment["sha256"]
        assert _sha256(record["text"].encode("utf-8")) == record["text_sha256"]


def test_parse_guide_html_extracts_official_sections() -> None:
    content = _read_guide_html()

    parsed = parse_guide_html(content, GUIDE_TITLE)

    assert parsed.department == "常州市数据局（常州市政务服务管理办公室）"
    assert parsed.title == GUIDE_TITLE
    assert set(parsed.sections) >= {
        "基本信息",
        "部门信息",
        "受理标准",
        "办理材料",
        "办理流程",
        "办理时限",
        "法律依据",
        "常见问题",
    }
    assert "## 办理材料" in parsed.text
    assert "《公司登记（备案）申请书》" in parsed.text
    assert "办理材料详情" not in parsed.text


def test_extract_attachment_urls_deduplicates() -> None:
    content = _read_guide_html()

    urls = extract_attachment_urls(content)

    assert len(urls) == 2
    assert len(urls) == len(set(urls))


def test_filename_from_content_disposition_handles_utf8() -> None:
    header = "attachment; filename*=UTF-8''%E5%85%AC%E5%8F%B8%E7%94%B3%E8%AF%B7.docx"

    assert filename_from_content_disposition(header) == "公司申请.docx"


def test_import_official_guides_with_mock_transport(tmp_path: Path) -> None:
    html_fixture = _read_guide_html().encode("utf-8")
    pdf_fixture = (FIXTURES / "company-change-guide.pdf").read_bytes()
    docx_fixture = (FIXTURES / "company-registration-form.docx").read_bytes()
    catalog_path = _write_catalog(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bszn.do"):
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html;charset=UTF-8"},
                content=html_fixture,
            )
        if request.url.path.endswith("/gzxxgztb_download.do"):
            return httpx.Response(
                200,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Disposition": (
                        "form-data; name=\"attachment\"; filename=\"company-guide.pdf\""
                    ),
                },
                content=pdf_fixture,
            )
        if request.url.host == "sxgl.jszwfw.gov.cn":
            query = parse_qs(urlparse(str(request.url)).query)
            guid = query["attachGuid"][0][-4:]
            return httpx.Response(
                200,
                headers={
                    "Content-Type": (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    "Content-Disposition": f'attachment; filename="form-{guid}.docx"',
                },
                content=docx_fixture,
            )
        return httpx.Response(404)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
    )
    output_path = tmp_path / "guides.jsonl"
    manifest_path = tmp_path / "manifest.json"
    raw_dir = tmp_path / "raw"

    summary = import_official_guides(
        catalog_path,
        output_path=output_path,
        manifest_path=manifest_path,
        raw_dir=raw_dir,
        client=client,
        generated_at=datetime(2026, 11, 24, tzinfo=UTC),
    )
    client.close()

    record = json.loads(output_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert summary.guide_count == 1
    assert summary.attachment_count == 2
    assert record["id"] == "cz-company-change-registration"
    assert record["department"] == "常州市数据局（常州市政务服务管理办公室）"
    assert record["source_url"].startswith(
        "https://cz.jszwfw.gov.cn/jszwfw/bscx/itemlist/bszn.do?"
    )
    assert record["source_retrieved_at"] == "2026-11-24T00:00:00Z"
    assert len(record["source_pdf_sha256"]) == 64
    assert len(record["text_sha256"]) == 64
    assert len(record["attachments"]) == 2
    assert (raw_dir / record["source_pdf_path"]).is_file()
    assert all((raw_dir / item["path"]).is_file() for item in record["attachments"])
    assert manifest["guides"][0]["source_pdf"]["remote_name"] == "company-guide.pdf"


def test_import_rejects_empty_pdf(tmp_path: Path) -> None:
    html_fixture = _read_guide_html().encode("utf-8")
    catalog_path = _write_catalog(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bszn.do"):
            return httpx.Response(200, content=html_fixture)
        if request.url.path.endswith("/gzxxgztb_download.do"):
            return httpx.Response(
                200,
                headers={"Content-Type": "application/pdf"},
                content=b"",
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(OfficialSourceError, match="返回空文件"):
        import_official_guides(
            catalog_path,
            output_path=tmp_path / "guides.jsonl",
            manifest_path=tmp_path / "manifest.json",
            raw_dir=tmp_path / "raw",
            client=client,
        )
    client.close()


def _read_guide_html() -> str:
    import gzip

    return gzip.decompress(
        (FIXTURES / "company-change-guide.html.gz").read_bytes()
    ).decode("utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_name": "江苏政务服务网·常州法人服务",
                "source_base_url": "https://cz.jszwfw.gov.cn",
                "list_url": "https://cz.jszwfw.gov.cn/jszwfw/bscx/itemlist/fr_index.do",
                "web_id": "5",
                "guides": [
                    {
                        "id": "cz-company-change-registration",
                        "title": GUIDE_TITLE,
                        "ql_kind": "01",
                        "yw_code": "113204000141102350332013104500202",
                        "ql_code": "1132040001411023503320131045002",
                        "tags": ["企业登记", "公司变更"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path
