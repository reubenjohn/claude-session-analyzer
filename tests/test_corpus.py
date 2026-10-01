"""Reading the forest: line numbers, skipping, project naming, filters."""
import fixtures as fx
from sa import corpus


def test_physical_line_numbers_survive_skipped_lines(tmp_path):
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": [
        fx.user_text("uuid-0001"),
        "{not json",
        "",
        "[1, 2]",
        fx.user_text("uuid-0002"),
    ]})
    loaded = corpus.load(root)
    (source,) = loaded.files
    assert [(r.line, r.data["uuid"]) for r in source.records] == [
        (1, "uuid-0001"), (5, "uuid-0002")]
    assert loaded.skipped_lines == 3
    assert loaded.duplicate_records == 0


def test_project_is_the_first_path_component_for_agents_too(tmp_path):
    root = fx.corpus(tmp_path, {
        "proj-b/sess-0001.jsonl": [fx.user_text("uuid-0001")],
        "proj-b/sess-0001/subagents/agent-fake1.jsonl": [fx.user_text("uuid-0002")],
        "proj-a/sess-0002.jsonl": [fx.user_text("uuid-0003")],
    })
    loaded = corpus.load(root)
    assert [(s.project, s.path.name) for s in loaded.files] == [
        ("proj-a", "sess-0002.jsonl"), ("proj-b", "sess-0001.jsonl"),
        ("proj-b", "agent-fake1.jsonl")]
    kept = corpus.load(root, keep=lambda path, project: project == "proj-a")
    assert [s.project for s in kept.files] == ["proj-a"]


def test_uuid_less_records_are_kept_and_never_deduped(tmp_path):
    bookkeeping = {"type": "mode", "mode": "default"}
    root = fx.corpus(tmp_path, {"proj-a/sess-0001.jsonl": [bookkeeping, bookkeeping]})
    loaded = corpus.load(root)
    assert len(loaded.files[0].records) == 2
    assert loaded.duplicate_records == 0
