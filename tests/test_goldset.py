import pytest

from backend.evals.goldset import GoldItem, load_goldset, save_goldset


def test_roundtrip(tmp_path):
    items = [
        GoldItem(
            id="q001",
            question="Quel framework backend ?",
            expected_note_paths=["Projets/X.md"],
            expected_answer_points=["Flask"],
            tags=["factual"],
        ),
        GoldItem(id="q002", question="Question sans réponse ?", tags=["negative"]),
    ]
    path = tmp_path / "goldset.jsonl"
    save_goldset(items, path)
    loaded = load_goldset(path)
    assert loaded == items
    assert loaded[1].is_negative


def test_duplicate_ids_rejected(tmp_path):
    path = tmp_path / "goldset.jsonl"
    path.write_text(
        '{"id": "q001", "question": "a", "tags": ["factual"]}\n'
        '{"id": "q001", "question": "b", "tags": ["factual"]}\n'
    )
    with pytest.raises(ValueError, match="duplicate id"):
        load_goldset(path)


def test_unknown_tag_rejected(tmp_path):
    path = tmp_path / "goldset.jsonl"
    path.write_text('{"id": "q001", "question": "a", "tags": ["typo-tag"]}\n')
    with pytest.raises(ValueError, match="unknown tags"):
        load_goldset(path)
