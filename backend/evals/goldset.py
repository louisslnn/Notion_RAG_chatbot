import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

VALID_TAGS = {"factual", "multi-note", "negative"}


@dataclass
class GoldItem:
    id: str
    question: str
    expected_note_paths: list[str] = field(default_factory=list)
    expected_answer_points: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def is_negative(self) -> bool:
        return "negative" in self.tags


def load_goldset(path: str | Path) -> list[GoldItem]:
    items: list[GoldItem] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as err:
            raise ValueError(f"{path}:{line_no}: invalid JSON ({err})") from err

        item = GoldItem(
            id=str(data["id"]),
            question=data["question"],
            expected_note_paths=list(data.get("expected_note_paths", [])),
            expected_answer_points=list(data.get("expected_answer_points", [])),
            tags=list(data.get("tags", [])),
        )
        if item.id in seen_ids:
            raise ValueError(f"{path}:{line_no}: duplicate id {item.id!r}")
        seen_ids.add(item.id)
        unknown = set(item.tags) - VALID_TAGS
        if unknown:
            raise ValueError(f"{path}:{line_no}: unknown tags {sorted(unknown)}")
        items.append(item)
    return items


def save_goldset(items: list[GoldItem], path: str | Path) -> None:
    lines = [json.dumps(asdict(item), ensure_ascii=False) for item in items]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
