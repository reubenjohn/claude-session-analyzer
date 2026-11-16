"""Corpora for the screen tests, each under a throwaway HOME so the root
prints as ``~``: ``wide`` (one window whose tool and command tables are
cut) and ``realistic`` (the shape of a real week: several projects, uuid
sessions, typed subagents, many tools and commands, replies, user text,
ambiguous gaps, a shrink, every peak band). The default-screen budget is
measured on ``realistic`` as well as on the README fixture, so the gate
sees what a user sees (UX_PRINCIPLES 2)."""
import json
import re

import fixtures as fx

# The wide corpus: one window, one call per tool use, each result exact.
WIDE = [("Bash", {"command": c}) for c in ("git status", "ls -la", "grep -r x .", "cat a.txt",
                                          "make all", "pytest -q", "echo hi")]
WIDE += [("Read", {"file_path": "/x/a.py"}), ("Edit", {"file_path": "/x/b.md"}),
         ("Write", {"file_path": "/x/c.txt"}), ("Grep", {"pattern": "x"}),
         ("Glob", {"pattern": "*.py"}), ("WebFetch", {"url": "https://example.com"})]


def _project(home, name):
    return home / ".claude" / "projects" / (re.sub(r"[^A-Za-z0-9]", "-", str(home)) + "-work-" + name)


def wide(home):
    records, size = [], 1000
    for i, (name, tool_input) in enumerate(WIDE):
        records.append(fx.assistant("uuid-%04d" % (2 * i + 1), "msg-%04d" % i, fx.usage(size, 10),
                                    [fx.tool_use("toolu_%04d" % i, name, **tool_input)]))
        records.append(fx.tool_result("uuid-%04d" % (2 * i + 2), "toolu_%04d" % i))
        size += 10 + 100 * (i + 1)  # the reply read back, then the result
    records.append(fx.assistant("uuid-9999", "msg-9999", fx.usage(size, 10)))
    fx.write_jsonl(_project(home, "wide") / "sess-0009.jsonl", records)


# The realistic corpus's tool uses, dealt round-robin: more tools and commands than a table shows.
USES = WIDE + [("Bash", {"command": c}) for c in ("python3 x.py", "sed -n 1p f", "rg x", "npm test",
                                                  "docker ps", "curl -s u", "jq . f", "find . -name x")]
USES += [("Read", {"file_path": "/x/d.%s" % ext}) for ext in ("json", "toml", "sh", "yaml")]
USES += [("Agent", {"prompt": "x"}), ("ToolSearch", {"query": "x"}), ("TodoWrite", {"todos": []})]
PROJECTS, SESSIONS, CALLS = 6, 2, 20  # per corpus, per project, per window
STARTS = (3000, 9000, 15000, 21000)  # a window's first call; its growth sets its peak band


def _id(n):
    """A fake uuid, plainly fake (the privacy gate's pattern aside)."""
    return "%08x-0000-4000-8000-%012x" % (0xabc00000 + n, n)


def _window(n, session, start, grow, agent=None):
    """One window of ``CALLS`` calls: a tool use per call, its result read
    back with the reply; every fourth gap batches two results (ambiguous),
    one gap shrinks, one brings user text."""
    u = lambda k: "u%03d-%04d" % (n, k)
    records, size, k = [], start, 0
    for c in range(CALLS):
        name, tool_input = USES[(n * 5 + c) % len(USES)]
        two = c % 4 == 3
        ids = ["t%03d-%02d" % (n, c)] + (["t%03d-%02db" % (n, c)] if two else [])
        blocks = [fx.tool_use(i, name, **tool_input) for i in ids]
        records.append(fx.assistant(u(k), "m%03d-%02d" % (n, c), fx.usage(size, 40 + c), blocks, session))
        records.append(fx.tool_result(u(k + 1), *ids, session=session))
        if c == 6:
            records.append(fx.user_text(u(k + 2), "go on", session))
        k += 3
        size += -300 if c == 9 else (40 + c) + grow * (1 + (n + c) % 5)
    records.append(fx.assistant(u(k), "m%03d-99" % n, fx.usage(size, 5), [], session))
    return [dict(r, agentId=agent) for r in records] if agent else records


def realistic(home):
    n = 0
    for p in range(PROJECTS):
        root = _project(home, "proj%d" % p)
        for s in range(SESSIONS):
            session = _id(100 * p + s)
            fx.write_jsonl(root / (session + ".jsonl"), _window(n, session, STARTS[n % 4], 650 * (1 + n % 6)))
            n += 1
            if s == 0:  # one typed subagent per project's first session
                agent = "a%07x%08x" % (0xb1e5ed0 + p, p)
                path = root / session / "subagents" / ("agent-%s.jsonl" % agent)
                fx.write_jsonl(path, _window(n, session, STARTS[n % 4], 650 * (1 + n % 6), agent))
                path.with_suffix(".meta.json").write_text(json.dumps({"agentType": "general-purpose"}))
                n += 1
