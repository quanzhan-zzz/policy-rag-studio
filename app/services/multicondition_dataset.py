import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
DATASET_NAME = "policy-multicondition-v1"
DATASET_PATH = DATA_DIR / f"{DATASET_NAME}.jsonl"
MANIFEST_PATH = DATA_DIR / f"{DATASET_NAME}.manifest.json"


@dataclass(frozen=True, slots=True)
class MultiConditionCase:
    id: str
    query: str
    expected_document_id: str
    expected_sections: tuple[str, ...]
    split: str
    constraint_summary: str


@lru_cache
def load_multicondition_cases(split: str = "test") -> tuple[MultiConditionCase, ...]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("多条件评测集校验和不匹配")
    cases: list[MultiConditionCase] = []
    for line in DATASET_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        case = MultiConditionCase(
            id=str(row["id"]),
            query=str(row["query"]),
            expected_document_id=str(row["expected_document_id"]),
            expected_sections=tuple(str(item) for item in row["expected_sections"]),
            split=str(row["split"]),
            constraint_summary=str(row["constraint_summary"]),
        )
        if split != "all" and case.split != split:
            continue
        cases.append(case)
    if split not in {"dev", "test", "all"}:
        raise ValueError(f"未知多条件切分：{split}")
    return tuple(cases)
