"""The doc caps AGENTS.md states, in bytes like the pre-commit size gates
(the docs print multi-byte marks such as ✓ and →, so bytes are the stricter
and unambiguous count)."""
import pytest

from fixtures import REPO

CAPS = {"README.md": 5000, "skills/session-analyzer/SKILL.md": 6000, "AGENTS.md": 7000, "CLAUDE.md": 100}


@pytest.mark.parametrize("name", sorted(CAPS))
def test_each_doc_is_within_its_cap(name):
    path = REPO / name
    assert path.is_file() and path.stat().st_size > 0, name  # vacuity guard: it exists, non-empty
    size = len(path.read_bytes())
    assert size <= CAPS[name], "%s is %d bytes, cap %d" % (name, size, CAPS[name])
