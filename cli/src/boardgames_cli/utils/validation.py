from __future__ import annotations

from typing import Sequence


def levenshtein(left: str, right: str) -> int:
    """
    Classic Levenshtein distance for fuzzy matching.
    """
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous_row = list(range(len(right) + 1))
    for i, char_left in enumerate(left, start=1):
        current_row = [i]
        for j, char_right in enumerate(right, start=1):
            insertions = previous_row[j] + 1
            deletions = current_row[j - 1] + 1
            substitutions = previous_row[j - 1] + (char_left != char_right)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def suggestions(target: str, candidates: Sequence[str], limit: int = 3) -> list[str]:
    """
    Suggest closest catalog entries to a missing game name.
    """
    normalized = [
        (candidate, levenshtein(target.lower(), candidate.lower()))
        for candidate in candidates
        if isinstance(candidate, str) and candidate
    ]
    normalized.sort(key=lambda item: item[1])
    return [name for name, _ in normalized[:limit]]


def format_missing(names: Sequence[str], catalog: Sequence[str], prefix: str) -> str:
    """
    Build a descriptive error message listing missing names and nearest neighbors.
    """
    explanations: list[str] = []
    for name in names:
        nearest = suggestions(name, catalog)
        if nearest:
            explanations.append(f"'{name}' (closest: {', '.join(nearest)})")
        else:
            explanations.append(f"'{name}'")
    return f"{prefix}: {'; '.join(explanations)}"
