import json

from backend.evals.runs import load_runs, markdown_report, write_run


def _fake_result(recall):
    return {
        "questions_evaluated": 2,
        "metrics": {"recall@1": recall, "mrr": recall},
        "by_tag": {"factual": {"recall@1": recall, "mrr": recall}},
        "questions": [],
    }


def test_write_run_and_report_roundtrip(tmp_path):
    runs_dir = tmp_path / "runs"
    path_a = write_run("retrieval", {"top_k": 4}, _fake_result(0.5), runs_dir=runs_dir)
    path_b = write_run("retrieval", {"top_k": 4}, _fake_result(0.75), runs_dir=runs_dir)
    # Same-second runs are rare in practice; tolerate collision for the test.
    if path_a == path_b:
        path_b = path_a

    payload = json.loads(path_a.read_text(encoding="utf-8"))
    assert payload["run_type"] == "retrieval"
    assert payload["git_sha"]
    assert payload["config"] == {"top_k": 4}

    runs = load_runs(runs_dir)
    assert runs
    report = markdown_report(runs)
    assert report.startswith("| metric |")
    assert "recall@1" in report
    assert "recall@1 [factual]" in report
    assert "0.750" in report


def test_report_handles_missing_metrics_across_runs(tmp_path):
    runs_dir = tmp_path / "runs"
    (runs_dir).mkdir()
    (runs_dir / "a.json").write_text(
        json.dumps({"run_type": "retrieval", "metrics": {"recall@1": 0.5}})
    )
    (runs_dir / "b.json").write_text(
        json.dumps({"run_type": "answers", "metrics": {"coverage": 0.9}})
    )

    report = markdown_report(load_runs(runs_dir))
    # Union of metrics as rows, missing values rendered as an em dash.
    assert "recall@1" in report and "coverage" in report
    assert "—" in report


def test_report_without_runs(tmp_path):
    (tmp_path / "runs").mkdir()
    assert "No eval runs" in markdown_report(load_runs(tmp_path / "runs"))
