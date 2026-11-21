from app.schemas import ChunkStrategy
from app.services.chunking import chunk_document
from app.services.seed import SEED_DOCUMENTS


def test_all_chunkers_create_content() -> None:
    document = SEED_DOCUMENTS[0]
    for strategy in ChunkStrategy:
        chunks = chunk_document(document.text, document.id, document.title, strategy)
        assert chunks
        assert all(chunk.text.strip() for chunk in chunks)
        assert all(chunk.id.startswith(f"{document.id}:{strategy.value}:") for chunk in chunks)


def test_heading_chunks_keep_heading_path() -> None:
    document = SEED_DOCUMENTS[0]
    chunks = chunk_document(
        document.text,
        document.id,
        document.title,
        ChunkStrategy.HEADING,
    )
    assert any("申请材料" in chunk.heading_path for chunk in chunks)
    assert any("办理时限" in chunk.heading_path for chunk in chunks)


def test_heading_chunks_skip_heading_only_title_chunk() -> None:
    text = "# 测试政策\n\n一、适用范围\n本政策用于测试。"
    chunks = chunk_document(text, "upload-test", "upload-file-name", ChunkStrategy.HEADING)
    assert [chunk.heading_path for chunk in chunks] == ["一、适用范围"]
    assert all(chunk.text.strip() != "# 测试政策" for chunk in chunks)
