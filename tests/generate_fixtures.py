#!/usr/bin/env python3
"""generate_fixtures.py — deterministic builder for the session-analyzer test
corpus. 100% SYNTHETIC/anonymized: invented UUIDs, placeholder prose, fake
/home/user/project paths. ZERO real transcript content.

Run:  python3 tests/generate_fixtures.py
Emits tests/fixtures/projects/-home-user-project/ mirroring the real on-disk
layout (`<session-id>.jsonl` + `<session-id>/subagents/agent-*.{jsonl,meta.json}`
+ a NESTED depth-3 grandchild). Every record shape is copied from the parser
contracts in scripts/lib/*.py — see tests/fixtures/README.md for the coverage map.

This file is the source of truth for the committed .jsonl fixtures; regenerate
after editing it. Runs on Python 3.8 (stdlib only).

PARITY ROLE MAP (D29 / R6-planner C1 P2) — the parity oracle
(scripts/check_v2_parity.py) and tests/test_parity_strings.py exercise four
role-SHAPED datasets built from these fixtures rather than duplicates; keep
the predicates intact when editing (they are pinned by test_role_predicates_*):
  forest — MAIN_ID session + subagents: depth-2 meta.json chain
           (agent-grand1: spawnDepth 2, parentAgentId child1)
  bypass — BYPASS_ID: uniform bypassPermissions, zero friction
  denial — SLICE_MAIN_ID: ≥1 observed denial + ≥1 interrupt, typed subagent
           (agent-rev1), missing-meta subagent (agent-mystery2), depth-2
           chain (agent-deep3 under agent-rev1)
  multi  — SLICE_MAIN_ID + SLICE_BG_ID aggregated together: overlapping
           top-level transcripts (per-transcript span sum 280s > 126s
           envelope) firing the span-sum-overlap caveat"""
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "fixtures", "projects", "-home-user-project")
# Separate project dir for the V2 fix-slice fixtures so session counts /
# orderings in -home-user-project stay stable for older tests.
SLICE_ROOT = os.path.join(HERE, "fixtures", "projects", "-home-user-sliceproj")

BASE = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def ts(sec):
    """Whole-second UTC offset -> Z-suffixed ms timestamp (parse_ts contract;
    regression anchor for the parse_ts UTC bug fixed in ~/.home 4ec06ac)."""
    return (BASE + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%S") + ".000Z"


# ---- record builders (shapes verified against real transcripts) ----
def user_text(uuid, sec, text, parent=None, pm="default"):
    r = {"parentUuid": parent, "type": "user", "uuid": uuid, "timestamp": ts(sec),
         "message": {"role": "user", "content": [{"type": "text", "text": text}]},
         "sessionId": None, "gitBranch": "main"}
    if pm:
        r["permissionMode"] = pm
    return r


def user_string(uuid, sec, text, parent=None, pm="default", extra=None):
    """User record whose message.content is a plain STRING (task-notifications
    arrive this way — keys as user:prompt in lib_turns._key)."""
    r = {"parentUuid": parent, "type": "user", "uuid": uuid, "timestamp": ts(sec),
         "message": {"role": "user", "content": text}, "gitBranch": "main"}
    if pm:
        r["permissionMode"] = pm
    if extra:
        r.update(extra)
    return r


def tool_result(uuid, sec, tuid, content, parent=None, pm="default", is_error=False):
    block = {"type": "tool_result", "tool_use_id": tuid, "content": content}
    if is_error:
        block["is_error"] = True
    r = {"parentUuid": parent, "type": "user", "uuid": uuid, "timestamp": ts(sec),
         "message": {"role": "user", "content": [block]}, "gitBranch": "main"}
    if pm:
        r["permissionMode"] = pm
    return r


def asst(uuid, sec, msg_id, blocks, usage, parent=None, pm="default",
         model="claude-opus-4-8"):
    r = {"parentUuid": parent, "type": "assistant", "uuid": uuid, "timestamp": ts(sec),
         "requestId": "req_" + msg_id,
         "message": {"id": msg_id, "role": "assistant", "model": model,
                     "content": blocks, "usage": usage},
         "gitBranch": "main"}
    if pm:
        r["permissionMode"] = pm
    return r


def usage(ctx, out, cache_creation=0):
    """context = input + cache_read + cache_creation (usage_context contract)."""
    inp = 4
    cache_read = ctx - inp - cache_creation
    return {"input_tokens": inp, "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation, "output_tokens": out}


def thinking(txt):
    return {"type": "thinking", "thinking": txt, "signature": "sig"}


def text(txt):
    return {"type": "text", "text": txt}


def tool_use(tuid, name, inp):
    return {"type": "tool_use", "id": tuid, "name": name, "input": inp}


def hook_success(uuid, sec, tuid, hook_event, duration_ms, hook_name):
    return {"parentUuid": None, "type": "attachment", "uuid": uuid, "timestamp": ts(sec),
            "attachment": {"type": "hook_success", "hookName": hook_name,
                           "toolUseID": tuid, "hookEvent": hook_event, "content": "",
                           "stdout": "", "stderr": "", "exitCode": 0,
                           "command": "bash hook.sh", "durationMs": duration_ms},
            "gitBranch": "main"}


def hook_context(uuid, sec, tuid, content_list, hook_event="PreToolUse"):
    return {"parentUuid": None, "type": "attachment", "uuid": uuid, "timestamp": ts(sec),
            "attachment": {"type": "hook_additional_context", "content": content_list,
                           "hookName": "PreToolUse:Agent", "toolUseID": tuid,
                           "hookEvent": hook_event}, "gitBranch": "main"}


def sys_turn_duration(uuid, sec, duration_ms):
    return {"parentUuid": None, "type": "system", "subtype": "turn_duration",
            "durationMs": duration_ms, "uuid": uuid, "timestamp": ts(sec),
            "gitBranch": "main"}


def sys_stop_hook(uuid, sec, infos):
    return {"parentUuid": None, "type": "system", "subtype": "stop_hook_summary",
            "hookCount": len(infos), "hookInfos": infos, "hookErrors": [],
            "uuid": uuid, "timestamp": ts(sec), "gitBranch": "main"}


def sys_away_summary(uuid, sec):
    return {"parentUuid": None, "type": "system", "subtype": "away_summary",
            "uuid": uuid, "timestamp": ts(sec), "gitBranch": "main"}


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


DENIAL = ("The user doesn't want to proceed with this tool use. The tool use "
          "was rejected (eg. if it was a file edit, the new_string was NOT "
          "written to the file). STOP what you are doing and wait for the user.")
INTERRUPT_1 = "[Request interrupted by user]"
INTERRUPT_2 = "[Request interrupted by user for tool use]"
TASK_NOTIF = ("<task-notification>\n<task-id>bg000fixture</task-id>\n"
              "<tool-use-id>tu_task1</tool-use-id>\n"
              "<output-file>/tmp/fixture/task-out.txt</output-file>\n"
              "The background subagent 'Investigate widget parser' has finished.\n"
              "</task-notification>")

MAIN_ID = "11111111-1111-4111-8111-111111111111"
BYPASS_ID = "22222222-2222-4222-8222-222222222222"
EDGE_ID = "33333333-3333-4333-8333-333333333333"


def build_main():
    """The rich session — covers streaming parse, max-merge disagreement, twin
    dedup, resumed-replay uuid drop, hooks, denial, both interrupts, compound
    bash, all three idle-gap cases (ordinary/F6/trailing), UTC timestamps."""
    R = []
    # TURN 1 — read
    R.append(user_text("uuid-0001", 0, "Fix the widget parser in /home/user/project"))
    R.append(asst("uuid-0002", 3, "m1",
                  [thinking("Let me inspect the parser module."),
                   tool_use("tu_read1", "Read", {"file_path": "/home/user/project/widget.py"})],
                  usage(8204, 300), parent="uuid-0001"))
    R.append(tool_result("uuid-0003", 4, "tu_read1",
                         "def parse_widget(): pass  # placeholder body", parent="uuid-0002"))
    # TURN 2 — compound bash (pipe), paired hook
    R.append(asst("uuid-0004", 6, "m2",
                  [text("Now search for TODOs."),
                   tool_use("tu_bash1", "Bash", {"command": "grep -rn TODO /home/user/project | head -20"})],
                  usage(8620, 180), parent="uuid-0003"))
    R.append(hook_success("uuid-0005", 6, "tu_bash1", "PreToolUse", 120, "PreToolUse:Bash"))
    R.append(tool_result("uuid-0006", 8, "tu_bash1", "widget.py:12: TODO handle nesting", parent="uuid-0004"))
    # TURN 3 — git push (dominant segment), 90s ordinary tool gap
    R.append(asst("uuid-0007", 10, "m3",
                  [text("Committing progress."),
                   tool_use("tu_bash2", "Bash", {"command": "git add -A && git commit -m 'wip' && git push origin main"})],
                  usage(8900, 150), parent="uuid-0006"))
    R.append(hook_success("uuid-0008", 10, "tu_bash2", "PreToolUse", 300, "PreToolUse:Bash"))
    R.append(tool_result("uuid-0009", 100, "tu_bash2", "To github.com/user/project.git\n  main -> main", parent="uuid-0007"))
    # TURN 4 — compound bash (pipe + semicolon)
    R.append(asst("uuid-0010", 103, "m4",
                  [text("Inspecting the log."),
                   tool_use("tu_bash3", "Bash", {"command": "cat /home/user/project/log.txt | grep ERROR ; echo done"})],
                  usage(9000, 90, cache_creation=500), parent="uuid-0009"))
    R.append(tool_result("uuid-0011", 104, "tu_bash3", "ERROR: none found\ndone", parent="uuid-0010"))
    # TURN 5 — known-wait sleep
    R.append(asst("uuid-0012", 106, "m5",
                  [text("Waiting for the daemon."),
                   tool_use("tu_bash4", "Bash", {"command": "sleep 5 && echo woke"})],
                  usage(9080, 60), parent="uuid-0011"))
    R.append(tool_result("uuid-0013", 112, "tu_bash4", "woke", parent="uuid-0012"))
    # TURN 6 — DENIAL
    R.append(asst("uuid-0014", 114, "m6",
                  [text("Removing the temp dir."),
                   tool_use("tu_bash5", "Bash", {"command": "rm -rf /home/user/project/tmp"})],
                  usage(9150, 70), parent="uuid-0013"))
    R.append(tool_result("uuid-0015", 120, "tu_bash5", DENIAL, parent="uuid-0014", is_error=True))
    # stop -> genuine waiting_for_user gap (78s)
    R.append(sys_turn_duration("uuid-0016", 121, 45000))
    R.append(sys_stop_hook("uuid-0017", 122,
                           [{"command": "bash stop-uncommitted.sh", "durationMs": 41}]))
    R.append(user_text("uuid-0018", 200, "Also please update the changelog."))
    # TURN 7 — INTERRUPT 1 (during text)
    R.append(asst("uuid-0019", 205, "m7", [text("I'll refactor the module extensively...")],
                  usage(9250, 200), parent="uuid-0018", pm="acceptEdits"))
    R.append(user_text("uuid-0020", 208, INTERRUPT_1, pm="acceptEdits"))
    # TURN 8 — INTERRUPT 2 (mid-tool; tu_bash6 left unmatched on purpose)
    R.append(asst("uuid-0021", 210, "m8",
                  [text("Starting the build."),
                   tool_use("tu_bash6", "Bash", {"command": "cargo build --workspace"})],
                  usage(9350, 80), parent="uuid-0020", pm="acceptEdits"))
    R.append(user_text("uuid-0022", 212, INTERRUPT_2, pm="acceptEdits"))
    # TWIN dedup — two records, same message.id, identical empty thinking block
    R.append(asst("uuid-000C", 214, "m_twin",
                  [thinking(""), text("Checking the test suite.")],
                  usage(9550, 40), parent="uuid-0022"))
    R.append(asst("uuid-000D", 215, "m_twin", [thinking("")], usage(9550, 40), parent="uuid-0022"))
    # MAX-MERGE DISAGREEMENT — two records, same message.id, output_tokens differ
    R.append(asst("uuid-000A", 216, "m_disagree",
                  [thinking("Weighing two parser strategies.")],
                  usage(9600, 900), parent="uuid-000D"))
    R.append(asst("uuid-000B", 217, "m_disagree",
                  [text("Going with recursive descent.")],
                  usage(9600, 650), parent="uuid-000A"))
    # RESUMED-REPLAY — duplicate uuid-0002; iter_records drops it (no double count)
    R.append(asst("uuid-0002", 218, "m1", [text("(replayed line — must be dropped)")],
                  usage(8204, 99999), parent="uuid-0001"))
    # SUBAGENT DISPATCH — two Task tool_use ids match the child meta.json toolUseId
    R.append(asst("uuid-0023", 220, "m9",
                  [text("Dispatching two research subagents."),
                   tool_use("tu_task1", "Task", {"description": "Investigate widget parser",
                                                  "subagent_type": "general-purpose"}),
                   tool_use("tu_task2", "Task", {"description": "Audit log format",
                                                 "subagent_type": "general-purpose"})],
                  usage(9800, 260), parent="uuid-000B", pm="bypassPermissions"))
    R.append(hook_success("uuid-0024", 221, "tu_task1", "PreToolUse", 11, "PreToolUse:Agent"))
    R.append(hook_context("uuid-0025", 222, "tu_task1",
                          ["Dispatch check — model tier ok; leaf isolation ok"]))
    # F6 GAP (300s) terminated by a background task-notification (string content).
    # V1 keys this as user:prompt -> waiting_for_user (KNOWN-WRONG; should be
    # waiting_for_subagent). Do NOT "fix" the fixture to dodge this.
    R.append(user_string("uuid-0026", 522, TASK_NOTIF, parent="uuid-0025",
                         extra={"promptSource": "system"}))
    # FINAL user-facing message
    R.append(asst("uuid-0027", 524, "m10",
                  [text("All done — widget parser fixed and changelog updated.")],
                  usage(9900, 140), parent="uuid-0026"))
    # TRAILING GAP (600s) after the final message — F6 says exclude it.
    R.append(sys_away_summary("uuid-0028", 1124))
    # summary record (no timestamp) — demonstrates the record type; gaps() skips it.
    R.append({"type": "summary", "summary": "Session: fixed the widget parser",
              "leafUuid": "uuid-0027"})
    write_jsonl(os.path.join(ROOT, MAIN_ID + ".jsonl"), R)


def build_bypass():
    """bypassPermissions-only session — prompts_possible=False path + bypass census."""
    R = [
        user_text("byp-0001", 0, "Run the smoke suite.", pm="bypassPermissions"),
        asst("byp-0002", 2, "bm1",
             [text("Running tests."),
              tool_use("byp_tu1", "Bash", {"command": "pytest -q && echo ok"})],
             usage(7000, 120), parent="byp-0001", pm="bypassPermissions"),
        tool_result("byp-0003", 4, "byp_tu1", "12 passed\nok", parent="byp-0002", pm="bypassPermissions"),
        asst("byp-0004", 6, "bm2", [text("All green.")], usage(7100, 60),
             parent="byp-0003", pm="bypassPermissions"),
    ]
    write_jsonl(os.path.join(ROOT, BYPASS_ID + ".jsonl"), R)


def build_edge():
    """Non-monotonic context (a cache-drop/clear reset) — exercises
    n_negative_deltas>0, CONTEXT_MONOTONIC_IDENTITY caveat, and the identity
    FAIL path (context_breakdown exits nonzero)."""
    R = [
        user_text("edg-0001", 0, "Continue after compaction."),
        asst("edg-0002", 2, "em1", [text("Boot.")], usage(5000, 100), parent="edg-0001"),
        asst("edg-0003", 4, "em2", [text("Grew.")], usage(12000, 200), parent="edg-0002"),
        asst("edg-0004", 6, "em3", [text("Reset (cache dropped).")], usage(3000, 90), parent="edg-0003"),
        asst("edg-0005", 8, "em4", [text("Regrew.")], usage(4000, 80), parent="edg-0004"),
    ]
    write_jsonl(os.path.join(ROOT, EDGE_ID + ".jsonl"), R)


def build_subagents():
    """Direct children (agent-child1/2) + a NESTED depth-3 grandchild
    (agent-child1/subagents/agent-grand1) that the current flat discover_subagents
    does NOT recurse into (F2 anchor)."""
    sub_dir = os.path.join(ROOT, MAIN_ID, "subagents")

    # child1 — itself dispatches grand1 (depth-2 Task)
    child1 = [
        user_text("c1-0001", 0, "Investigate the widget parser and report findings."),
        asst("c1-0002", 2, "c1m1",
             [thinking("Reading the parser (CLAUDE.md inherited -> high boot)."),
              tool_use("c1_tu1", "Read", {"file_path": "/home/user/project/widget.py"})],
             usage(20000, 400), parent="c1-0001"),
        tool_result("c1-0003", 3, "c1_tu1", "def parse_widget(): ...", parent="c1-0002"),
        asst("c1-0004", 5, "c1m2",
             [text("Dispatching a coverage sub-check."),
              tool_use("tu_task_g1", "Task", {"description": "Check test coverage",
                                              "subagent_type": "general-purpose"})],
             usage(20500, 200), parent="c1-0003"),
        asst("c1-0005", 8, "c1m3", [text("Findings: parser handles nested widgets.")],
             usage(20700, 150), parent="c1-0004"),
    ]
    write_jsonl(os.path.join(sub_dir, "agent-child1.jsonl"), child1)
    with open(os.path.join(sub_dir, "agent-child1.meta.json"), "w") as f:
        json.dump({"agentType": "general-purpose", "description": "Investigate widget parser",
                   "toolUseId": "tu_task1", "spawnDepth": 1, "parentAgentId": None,
                   "model": "claude-opus-4-8"}, f, indent=2)

    # child2 — leaf child
    child2 = [
        user_text("c2-0001", 0, "Audit the log format."),
        asst("c2-0002", 2, "c2m1",
             [text("Scanning logs."),
              tool_use("c2_tu1", "Bash", {"command": "grep -c ERROR /home/user/project/log.txt"})],
             usage(19000, 180), parent="c2-0001"),
        tool_result("c2-0003", 3, "c2_tu1", "0", parent="c2-0002"),
        asst("c2-0004", 5, "c2m2", [text("Log format is JSON lines.")],
             usage(19200, 120), parent="c2-0003"),
    ]
    write_jsonl(os.path.join(sub_dir, "agent-child2.jsonl"), child2)
    with open(os.path.join(sub_dir, "agent-child2.meta.json"), "w") as f:
        json.dump({"agentType": "general-purpose", "description": "Audit log format",
                   "toolUseId": "tu_task2", "spawnDepth": 1, "parentAgentId": None,
                   "model": "claude-opus-4-8"}, f, indent=2)

    # grand1 — NESTED under child1 (depth-3 chain: main -> child1 -> grand1)
    grand_dir = os.path.join(sub_dir, "agent-child1", "subagents")
    grand1 = [
        user_text("g1-0001", 0, "Check test coverage for the widget parser."),
        asst("g1-0002", 2, "g1m1",
             [text("Running the test suite."),
              tool_use("g1_tu1", "Bash", {"command": "pytest -q tests/test_widget.py"})],
             usage(21000, 160), parent="g1-0001"),
        tool_result("g1-0003", 3, "g1_tu1", "5 passed", parent="g1-0002"),
        asst("g1-0004", 5, "g1m2", [text("Coverage is 92%.")], usage(21100, 90), parent="g1-0003"),
    ]
    write_jsonl(os.path.join(grand_dir, "agent-grand1.jsonl"), grand1)
    with open(os.path.join(grand_dir, "agent-grand1.meta.json"), "w") as f:
        json.dump({"agentType": "general-purpose", "description": "Check test coverage",
                   "toolUseId": "tu_task_g1", "spawnDepth": 2, "parentAgentId": "child1",
                   "model": "claude-opus-4-8"}, f, indent=2)


SLICE_MAIN_ID = "55555555-5555-4555-8555-555555555555"
SLICE_BG_ID = "66666666-6666-4666-8666-666666666666"

# 400-char ad-hoc python -c command: the len>300 deny-hook trigger (D3) must be
# reachable from the FULL command even though previews truncate at 200.
LONG_PY = ("python -c 'print(\"synthetic fixture inline script\")' # " + "pad" * 115)[:400]


def build_slice_main():
    """Fix-slice session: mixed observed modes (default + acceptEdits), one
    observed DENIAL + one INTERRUPT (D1/D19), a 400-char python -c command
    (D3), and two Task dispatches whose subagent transcripts carry typed /
    missing meta.json evidence (D13). The final gap ends in a Task-mapped
    task-notification so it stays waiting_for_subagent (D20 control)."""
    R = []
    R.append(user_text("sl-0001", 0, "Refactor the widget renderer."))
    R.append(asst("sl-0002", 2, "sm1",
                  [text("Running an inline check."),
                   tool_use("sl_tu1", "Bash", {"command": LONG_PY})],
                  usage(8000, 120), parent="sl-0001"))
    R.append(tool_result("sl-0003", 4, "sl_tu1", "synthetic fixture inline script", parent="sl-0002"))
    # DENIAL
    R.append(asst("sl-0004", 6, "sm2",
                  [text("Cleaning caches."),
                   tool_use("sl_tu2", "Bash", {"command": "rm -rf /home/user/project/cache"})],
                  usage(8200, 90), parent="sl-0003"))
    R.append(tool_result("sl-0005", 10, "sl_tu2", DENIAL, parent="sl-0004", is_error=True))
    R.append(sys_turn_duration("sl-0006", 11, 9000))
    R.append(user_text("sl-0007", 40, "Skip the cache; just fix rendering.", pm="acceptEdits"))
    # INTERRUPT
    R.append(asst("sl-0008", 42, "sm3", [text("Rewriting the renderer wholesale...")],
                  usage(8400, 150), parent="sl-0007", pm="acceptEdits"))
    R.append(user_text("sl-0009", 45, INTERRUPT_1, pm="acceptEdits"))
    # Subagent dispatches (typed + one with missing meta)
    R.append(asst("sl-0010", 48, "sm4",
                  [text("Dispatching review and audit agents."),
                   tool_use("sl_task1", "Task", {"description": "Review widget renderer diff",
                                                 "subagent_type": "code-reviewer"}),
                   tool_use("sl_task2", "Task", {"description": "Audit renderer styles",
                                                 "subagent_type": "general-purpose"})],
                  usage(8700, 200), parent="sl-0009", pm="acceptEdits"))
    # 60s subagent wait terminated by a Task-mapped task-notification
    notif = ("<task-notification>\n<task-id>bg111fixture</task-id>\n"
             "<tool-use-id>sl_task1</tool-use-id>\n"
             "<output-file>/tmp/fixture/slice-task.txt</output-file>\n"
             "The subagent 'Review widget renderer diff' has finished.\n"
             "</task-notification>")
    R.append(user_string("sl-0011", 108, notif, parent="sl-0010",
                         extra={"promptSource": "system"}))
    R.append(asst("sl-0012", 110, "sm5", [text("Renderer fixed; review incorporated.")],
                  usage(8900, 110), parent="sl-0011"))
    write_jsonl(os.path.join(SLICE_ROOT, SLICE_MAIN_ID + ".jsonl"), R)

    sub_dir = os.path.join(SLICE_ROOT, SLICE_MAIN_ID, "subagents")
    # typed reviewer child with meta.json (agentType evidence)
    rev1 = [
        user_text("sr-0001", 50, "Review the widget renderer diff."),
        asst("sr-0002", 52, "srm1",
             [text("Reading the diff."),
              tool_use("sr_tu1", "Read", {"file_path": "/home/user/project/renderer.py"})],
             usage(15000, 220), parent="sr-0001"),
        tool_result("sr-0003", 54, "sr_tu1", "def render(): ...", parent="sr-0002"),
        asst("sr-0004", 90, "srm2", [text("Review: rendering path is sound.")],
             usage(15200, 160), parent="sr-0003"),
    ]
    write_jsonl(os.path.join(sub_dir, "agent-rev1.jsonl"), rev1)
    with open(os.path.join(sub_dir, "agent-rev1.meta.json"), "w") as f:
        json.dump({"agentType": "code-reviewer", "description": "Review widget renderer diff",
                   "toolUseId": "sl_task1", "spawnDepth": 1, "parentAgentId": None,
                   "model": "claude-opus-4-8"}, f, indent=2)

    # child WITHOUT meta.json — agent_type must be reported unknown, never assumed
    mystery = [
        user_text("sy-0001", 51, "Audit renderer styles."),
        asst("sy-0002", 53, "sym1", [text("Styles audited: consistent.")],
             usage(14000, 130), parent="sy-0001"),
    ]
    write_jsonl(os.path.join(sub_dir, "agent-mystery2.jsonl"), mystery)

    # depth-2 grandchild under rev1 with parentAgentId/spawnDepth meta chain
    deep_dir = os.path.join(sub_dir, "agent-rev1", "subagents")
    deep = [
        user_text("sd-0001", 56, "Check renderer test coverage."),
        asst("sd-0002", 58, "sdm1", [text("Coverage is 88%.")],
             usage(16000, 90), parent="sd-0001"),
    ]
    write_jsonl(os.path.join(deep_dir, "agent-deep3.jsonl"), deep)
    with open(os.path.join(deep_dir, "agent-deep3.meta.json"), "w") as f:
        json.dump({"agentType": "general-purpose", "description": "Check renderer test coverage",
                   "toolUseId": "sr_task_d1", "spawnDepth": 2, "parentAgentId": "rev1",
                   "model": "claude-opus-4-8"}, f, indent=2)


def build_slice_bg():
    """Zero-subagent bypass session whose only task-notification comes from a
    BACKGROUND Bash task (D20): waiting_for_subagent must be 0; the wait lands
    in waiting_for_tool with notification_kind=background_task. Uniform
    bypassPermissions also pins D19's 'uniform observed mode' provenance."""
    notif = ("<task-notification>\n<task-id>bg222fixture</task-id>\n"
             "<tool-use-id>sb_tu1</tool-use-id>\n"
             "<output-file>/tmp/fixture/bg-task.txt</output-file>\n"
             "The background command has finished.\n"
             "</task-notification>")
    R = [
        user_text("sb-0001", 0, "Run the long build in the background.", pm="bypassPermissions"),
        asst("sb-0002", 2, "sbm1",
             [text("Starting the background build."),
              tool_use("sb_tu1", "Bash", {"command": "make build-all",
                                          "run_in_background": True})],
             usage(6000, 100), parent="sb-0001", pm="bypassPermissions"),
        tool_result("sb-0003", 4, "sb_tu1", "Command running in background", parent="sb-0002", pm="bypassPermissions"),
        user_string("sb-0004", 124, notif, pm="bypassPermissions",
                    extra={"promptSource": "system"}),
        asst("sb-0005", 126, "sbm2", [text("Background build finished clean.")],
             usage(6200, 80), parent="sb-0004", pm="bypassPermissions"),
    ]
    write_jsonl(os.path.join(SLICE_ROOT, SLICE_BG_ID + ".jsonl"), R)


QUEUE_ROOT = os.path.join(HERE, "fixtures", "projects", "-home-user-queueproj")
QUEUE_ID = "88888888-8888-4888-8888-888888888888"


def queue_op(sec):
    """BARE queue-operation record (no task-notification, NO content): the
    scheduled dequeue/wake shape. Live scheduled dequeues carry no content
    key at all; only these mark a queue wake (F2 / fix-wave M1)."""
    return {"type": "queue-operation", "operation": "dequeue",
            "sessionId": QUEUE_ID, "timestamp": ts(sec)}


def queue_enqueue(sec, content):
    """Content-bearing queue-operation enqueue (live shape). Authorship is
    NOT in this record: human-typed and scheduler-fired enqueues share it.
    A scheduler-fired cluster is marked by the system:scheduled_task_fire
    record that follows it (W2-M4); without that marker an enqueue-with-text
    is a human prompt arriving, never a scheduled queue wake."""
    return {"type": "queue-operation", "operation": "enqueue",
            "content": content, "sessionId": QUEUE_ID, "timestamp": ts(sec)}


def sys_scheduled_fire(uuid, sec):
    """system:scheduled_task_fire — the structural marker the harness writes
    directly after a scheduler-fired queue-op cluster (live bg-session shape:
    enqueue -> dequeue -> scheduled_task_fire -> delivered isMeta prompt)."""
    return {"parentUuid": None, "type": "system", "subtype": "scheduled_task_fire",
            "content": "Running scheduled task", "uuid": uuid, "timestamp": ts(sec),
            "gitBranch": "main"}


def build_queue_bg():
    """Background/scheduled session pinning the queue-wake discriminator
    (F2 / W2-M4). waiting_for_user gaps, in order:
      60s -> BARE dequeue                       -> wake (no content)
      60s -> enqueue with HUMAN-typed text      -> NOT a wake (no fire marker)
      45s -> scheduler-fired enqueue with text  -> wake (scheduled_task_fire
             follows its cluster), + the 1s intra-cluster bare dequeue gap
             (wake) and the 1s fire->delivered-prompt gap (not flagged)
      30s -> real direct human prompt           -> NOT a wake
    => queue_wake_count == 3 (106s) of 6 active gaps (197s).
    Uniform bypassPermissions."""
    R = [
        user_text("qw-0001", 0, "Watch CI and re-check on the wake queue.", pm="bypassPermissions"),
        asst("qw-0002", 2, "qm1",
             [text("Checking CI status."),
              tool_use("qw_tu1", "Bash", {"command": "gh run list --limit 1"})],
             usage(6000, 90), parent="qw-0001", pm="bypassPermissions"),
        tool_result("qw-0003", 4, "qw_tu1", "completed success", parent="qw-0002", pm="bypassPermissions"),
        sys_turn_duration("qw-0004", 5, 4000),
        # 60s scheduled queue-wake gap (BARE dequeue terminator, no content).
        queue_op(65),
        asst("qw-0005", 67, "qm2", [text("Still green after wake one.")],
             usage(6100, 60), parent="qw-0003", pm="bypassPermissions"),
        sys_turn_duration("qw-0006", 68, 3000),
        # 60s gap ending in an enqueue WITH human-typed text and NO fire
        # marker: a human prompt arriving through the queue — never a wake.
        queue_enqueue(128, "Also check the flaky integration job when you wake."),
        asst("qw-0007", 130, "qm3", [text("Noted; will check the flaky job too.")],
             usage(6200, 55), parent="qw-0005", pm="bypassPermissions"),
        sys_turn_duration("qw-0008", 131, 2500),
        # 45s scheduler-fired cluster (live shape): enqueue-with-text ->
        # bare dequeue -> scheduled_task_fire -> delivered isMeta prompt.
        # The fire marker makes BOTH queue-op gaps scheduled wakes; the
        # delivered prompt gap stays waiting_for_user but unflagged.
        queue_enqueue(176, "scheduled poll: re-check CI status."),
        queue_op(177),
        sys_scheduled_fire("qw-0009", 177),
        user_string("qw-0010", 178, "scheduled poll: re-check CI status.",
                    parent="qw-0007", pm="bypassPermissions",
                    extra={"promptSource": "system", "isMeta": True}),
        asst("qw-0011", 180, "qm4", [text("Wake two: still green.")],
             usage(6300, 50), parent="qw-0010", pm="bypassPermissions"),
        sys_turn_duration("qw-0012", 181, 2000),
        # 30s REAL human prompt gap: the waiting_for_user denominator must
        # exceed the queue-wake count.
        user_text("qw-0013", 211, "Stop watching; summarize the run.", pm="bypassPermissions"),
        asst("qw-0014", 213, "qm5", [text("CI stayed green across both wakes.")],
             usage(6400, 70), parent="qw-0013", pm="bypassPermissions"),
    ]
    write_jsonl(os.path.join(QUEUE_ROOT, QUEUE_ID + ".jsonl"), R)


ORIGIN_ROOT = os.path.join(HERE, "fixtures", "projects", "-home-user-originproj")
ORIGIN_ID = "77777777-7777-4777-8777-777777777777"

HOOK_DENIAL = ("PreToolUse:Bash hook blocked this command: ad-hoc interpreter "
               "scripts must be committed files (hook exited 2)")
REJECTED_ONLY = "The tool use was rejected by policy."


def build_origin():
    """Denial-anchoring session (round-2 r1 F4 / r2 F5). Zero subagents (also
    pins the no-fabricated-agent-type-node contract, r1 F2). Contents:
      - a NON-error grep result QUOTING the denial marker mid-content -> 0
      - an ERROR result quoting the marker mid-content (not leading)   -> 0
      - a leading prompt-denial echo                    -> denial origin prompt
      - a hook-block error result                       -> denial origin hook
      - a bare rejected echo without prompt/hook marker -> denial origin unknown
    """
    quoting = ("docs/notes.md:12: the harness emits '" + DENIAL[:51] + "' on denial\n"
               "docs/notes.md:40: quoting the marker must never count")
    R = []
    R.append(user_text("or-0001", 0, "Audit permission friction handling."))
    R.append(asst("or-0002", 2, "om1",
                  [text("Searching docs for the denial marker."),
                   tool_use("or_tu1", "Bash", {"command": "grep -rn 'proceed with this tool use' docs/"})],
                  usage(7000, 90), parent="or-0001"))
    R.append(tool_result("or-0003", 4, "or_tu1", quoting, parent="or-0002"))
    R.append(asst("or-0004", 6, "om2",
                  [text("Reading the friction log."),
                   tool_use("or_tu2", "Bash", {"command": "cat /home/user/project/friction.log"})],
                  usage(7100, 80), parent="or-0003"))
    R.append(tool_result("or-0005", 8, "or_tu2",
                         "command failed; last log line: " + DENIAL[:51],
                         parent="or-0004", is_error=True))
    R.append(asst("or-0006", 10, "om3",
                  [text("Clearing the cache."),
                   tool_use("or_tu3", "Bash", {"command": "rm -rf /home/user/project/cache"})],
                  usage(7200, 70), parent="or-0005"))
    R.append(tool_result("or-0007", 12, "or_tu3", DENIAL, parent="or-0006", is_error=True))
    R.append(asst("or-0008", 14, "om4",
                  [text("Running an inline check."),
                   tool_use("or_tu4", "Bash", {"command": "python -c 'print(1)'"})],
                  usage(7300, 60), parent="or-0007"))
    R.append(tool_result("or-0009", 16, "or_tu4", HOOK_DENIAL, parent="or-0008", is_error=True))
    R.append(asst("or-0010", 18, "om5",
                  [text("Trying the edit again."),
                   tool_use("or_tu5", "Bash", {"command": "touch /home/user/project/marker"})],
                  usage(7400, 50), parent="or-0009"))
    R.append(tool_result("or-0011", 20, "or_tu5", REJECTED_ONLY, parent="or-0010", is_error=True))
    R.append(asst("or-0012", 22, "om6", [text("Friction audit complete.")],
                  usage(7500, 40), parent="or-0011"))
    write_jsonl(os.path.join(ORIGIN_ROOT, ORIGIN_ID + ".jsonl"), R)


def main():
    build_main()
    build_bypass()
    build_edge()
    build_subagents()
    build_slice_main()
    build_slice_bg()
    build_queue_bg()
    build_origin()
    print("wrote fixtures under", ROOT)
    print("wrote fixtures under", SLICE_ROOT)
    print("wrote fixtures under", QUEUE_ROOT)
    print("wrote fixtures under", ORIGIN_ROOT)


if __name__ == "__main__":
    main()
