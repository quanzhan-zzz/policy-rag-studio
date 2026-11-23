import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.seed import EVALUATION_CASES, EvaluationCase

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
SYNTHETIC_DATASET = "policy-synthetic-v1"
OFFICIAL_DATASET = "policy-official-v1"
SUPPORTED_DATASETS = {SYNTHETIC_DATASET, OFFICIAL_DATASET}


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    name: str
    split: str
    cases: tuple[EvaluationCase, ...]


@lru_cache
def _load_cases(name: str) -> tuple[EvaluationCase, ...]:
    path = DATA_DIR / f"{name}.jsonl"
    cases: list[EvaluationCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if str(row.get("dataset", name)) != name:
            raise ValueError(f"评测集 {name} 包含其他数据集的样本：{row['id']}")
        cases.append(
            EvaluationCase(
                id=str(row["id"]),
                query=str(row["query"]),
                expected_document_id=str(row["expected_document_id"]),
                expected_heading=str(row["expected_heading"]),
                failure_type=str(row["failure_type"]),
                split=str(row["split"]),
                gold_evidence=str(row["gold_evidence"]) if row.get("gold_evidence") else None,
            )
        )
    identifiers = [case.id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("评测集包含重复 ID")
    queries = [case.query for case in cases]
    if len(queries) != len(set(queries)):
        raise ValueError("评测集包含重复问题")
    splits = {case.split for case in cases}
    if not splits <= {"dev", "test"}:
        raise ValueError("评测集切分只能是 dev 或 test")
    return tuple(cases)


def get_evaluation_dataset(
    name: str = SYNTHETIC_DATASET,
    split: str = "test",
) -> EvaluationDataset:
    if name == "smoke":
        return EvaluationDataset(
            name="smoke",
            split="smoke",
            cases=EVALUATION_CASES,
        )
    if name not in SUPPORTED_DATASETS:
        raise ValueError(f"未知评测集：{name}")
    if split not in {"dev", "test", "all"}:
        raise ValueError(f"未知评测集切分：{split}")
    all_cases = _load_cases(name)
    cases = (
        all_cases
        if split == "all"
        else tuple(case for case in all_cases if case.split == split)
    )
    return EvaluationDataset(name=name, split=split, cases=cases)
