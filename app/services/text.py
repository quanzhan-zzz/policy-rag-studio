import re

TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")
STOPWORDS = {
    "的",
    "了",
    "和",
    "与",
    "及",
    "或",
    "在",
    "是",
    "有",
    "为",
    "对",
    "中",
    "等",
    "请",
    "如何",
    "哪些",
}


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/English text without external model dependencies.

    Chinese text produces unigrams and bigrams. This keeps the demo self-contained while
    still allowing exact policy names and short clauses to match.
    """
    base = [token.lower() for token in TOKEN_RE.findall(text) if token not in STOPWORDS]
    chinese = [token for token in base if re.fullmatch(r"[\u4e00-\u9fff]", token)]
    bigrams = [chinese[index] + chinese[index + 1] for index in range(len(chinese) - 1)]
    return base + bigrams


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
