import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.seed import EVALUATION_CASES, EvaluationCase

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"
SYNTHETIC_DATASET = "policy-synthetic-v1"


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    name: str
    split: str
    cases: tuple[EvaluationCase, ...]


@lru_cache
def _load_synthetic_cases() -> tuple[EvaluationCase, ...]:
    path = DATA_DIR / f"{SYNTHETIC_DATASET}.jsonl"
    cases: list[EvaluationCase] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cases.append(
            EvaluationCase(
                id=str(row["id"]),
                query=str(row["query"]),
                expected_document_id=str(row["expected_document_id"]),
                expected_heading=str(row["expected_heading"]),
                failure_type=str(row["failure_type"]),
                split=str(row["split"]),
            )
        )
    identifiers = [case.id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("评测集包含重复 ID")
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
    if name != SYNTHETIC_DATASET:
        raise ValueError(f"未知评测集：{name}")
    if split not in {"dev", "test", "all"}:
        raise ValueError(f"未知评测集切分：{split}")
    all_cases = _load_synthetic_cases()
    cases = (
        all_cases
        if split == "all"
        else tuple(case for case in all_cases if case.split == split)
    )
    return EvaluationDataset(name=name, split=split, cases=cases)
