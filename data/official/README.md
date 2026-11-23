# Official Source Corpus

由 `app/experiments/import_official_guides.py` 从 `data/sources/jszwfw/catalog.json` 生成。

```bash
uv run python -m app.experiments.import_official_guides
```

生成物：

- `jszwfw-guides.v1.jsonl`：RAG 可用的规范化正文及 provenance
- `jszwfw-guides.v1.manifest.json`：官方指南 PDF、材料附件、URL、大小与 SHA-256
- `raw/jszwfw/`：官方原始文件，便于复核提取结果

规范化 JSONL 中的 `source_url` 指向抓取时的事项详情页。PDF 与附件保留在 `raw/`，`source_pdf_sha256` 和 `text_sha256` 可用于检测上游更新。

本目录中的数据仅用于公开政策检索研究和演示。运行导入脚本时请遵守来源网站的使用规则，并保留抓取时间与原始哈希。
