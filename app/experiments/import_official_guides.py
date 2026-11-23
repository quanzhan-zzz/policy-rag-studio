import argparse
from pathlib import Path

from app.services.official_sources import OfficialSourceError, import_official_guides

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "data" / "sources" / "jszwfw" / "catalog.json"
DEFAULT_OUTPUT = ROOT / "data" / "official" / "jszwfw-guides.v1.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "official" / "jszwfw-guides.v1.manifest.json"
DEFAULT_RAW_DIR = ROOT / "data" / "official" / "raw" / "jszwfw"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="下载并规范化江苏政务服务网办事指南。"
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        summary = import_official_guides(
            args.catalog,
            output_path=args.output,
            manifest_path=args.manifest,
            raw_dir=args.raw_dir,
        )
    except OfficialSourceError as error:
        raise SystemExit(f"导入失败：{error}") from error
    print(
        f"导入 {summary.guide_count} 份官方指南、"
        f"{summary.attachment_count} 个材料附件 -> {summary.output_path}"
    )


if __name__ == "__main__":
    main()
