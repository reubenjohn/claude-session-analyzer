"""Can a cold agent learn and use `sa` from its own output alone?

Per persona, the journeys of evals/tasks.json run in ONE `claude -p` session,
in order; a `cold` or held-out journey gets a fresh agent of its own. A temp
dir outside the repo, Bash(python3 -m sa ...) and Read, a frozen snapshot; the
wrapper logs what the CLI printed; a second `claude -p` (sonnet) grades each
answer. Per journey and principle, never one score. See evals/README.md.
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_scorecard import scorecard  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
SA_CMD = re.compile(r"(^|[;&|]\s*)\s*(sa|python3 -m sa)(\s|$)")  # after any `cd X;` prefix
ISOLATE = ["--setting-sources", "", "--strict-mcp-config",
           "--disable-slash-commands", "--no-session-persistence"]



def load_tasks(args):
    """Groups of (persona, task, run): each group is one agent session, its
    journeys in tasks.json order; a cold or held-out journey (or any, with
    --fresh) is a group of its own."""
    tasks = json.loads((EVALS / "tasks.json").read_text())["tasks"]
    want = set(args.tasks.split(",")) if args.tasks else None
    chosen = [t for t in tasks if (want is None or t["id"] in want)
              and not (t.get("held_out") and not (args.include_held_out or want))]
    groups = []
    for p in args.personas.split(","):
        for n in range(1, args.repeat + 1):
            mine = [(p, t, n) for t in chosen if p in t["personas"]]
            alone = [j for j in mine if args.fresh or j[1].get("cold") or j[1].get("held_out")]
            groups += [[j] for j in alone] + ([[j for j in mine if j not in alone]] if len(alone) < len(mine) else [])
    return groups


def snapshot(home, snap, days):
    """Recent files, mtimes kept; no `-tmp-` project (eval runs' own)."""
    cutoff = time.time() - days * 86400
    for f in home.rglob("*"):
        rel = f.relative_to(home)
        if f.is_file() and not rel.parts[0].startswith("-tmp-") and f.stat().st_mtime >= cutoff:
            (snap / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, snap / rel)


def setup(tmp, args):
    snap, src, bin_ = tmp / "corpus", tmp / "src", tmp / "bin"
    snapshot(Path.home() / ".claude" / "projects", snap, args.days)
    if args.rev:
        subprocess.run(["git", "worktree", "add", "--detach", str(src), args.rev],
                       cwd=REPO, check=True, capture_output=True)
    else:
        src = REPO
    bin_.mkdir()
    shutil.copy(EVALS / "sa_wrapper.py", bin_ / "sa_wrapper.py")
    env = "SA_PY=%s SA_SRC=%s SA_ROOT=%s" % (sys.executable, src, snap)
    (bin_ / "sa").write_text('#!/bin/sh\n%s exec %s %s/sa_wrapper.py "$@"\n'
                             % (env, sys.executable, bin_))
    (bin_ / "python3").write_text(
        '#!/bin/sh\nif [ "$1" = -m ] && [ "$2" = sa ]; then shift 2; exec %s/sa "$@"; fi\n'
        'exec %s "$@"\n' % (bin_, sys.executable))
    for s in ("sa", "python3"):
        (bin_ / s).chmod(0o755)
    n = sum(1 for f in snap.rglob("*") if f.is_file())
    return src, bin_, n


def agent_cmd(persona, task, args, session=None, resume=False):
    """A fresh agent; in a session, the first journey names the session and
    each later one resumes it with the question part of the prompt alone."""
    prompt = (EVALS / "agent_prompt.md").read_text()
    prompt = prompt[prompt.index("Question:"):] if resume else prompt
    prompt = prompt.format(question=task["question"], persona=(
        EVALS / "personas" / (persona + ".md")).read_text().strip())
    isolate = ISOLATE if session is None else [x for x in ISOLATE if x != "--no-session-persistence"]
    return ["claude", "-p", prompt] + ([("--resume" if resume else "--session-id"), session] if session else []) + [ "--output-format", "stream-json", "--verbose",
           "--tools", "Bash,Read", "--allowedTools", "Bash(python3 -m sa)", "Bash(python3 -m sa *)", "Read",
           "--permission-mode", "dontAsk", "--max-budget-usd", str(args.budget)] + isolate + (
        ["--model", args.model] if args.model else [])


def sh(cmd, bin_, cwd, timeout=None, log=""):
    env = dict(os.environ, SA_LOG=str(log))
    env["PATH"] = "%s:%s" % (bin_, env["PATH"])
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=timeout, shell=isinstance(cmd, str))


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))


def measure(events, src, log):
    """Agent side from the transcript; what the CLI printed from the wrapper log."""
    runs = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    final = next((e for e in events if e.get("type") == "result"), {})
    denied = {d.get("tool_use_id") for d in final.get("permission_denials") or []}
    uses, session = {}, []
    m = dict(sa_cmds=0, piped=0, denied=len(denied), source_reads=0, reads=[], first=None,
             error_exits=sum(r["exit"] != 0 for r in runs),
             max_lines=max([r["lines"] for r in runs] or [0]),
             max_width=max([r["width"] for r in runs] or [0]),
             gates=["sa %s: %s" % (" ".join(r["argv"]), g) for r in runs for g in r["gates"]])
    for e in events:
        msg = e.get("message") if isinstance(e, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for c in content if isinstance(content, list) else []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use":
                uses[c["id"]] = (c["name"], c.get("input", {}))
                if c["name"] == "Read":
                    p = c["input"].get("file_path", "")
                    m["reads"].append(p)
                    m["source_reads"] += "/sa/" in p and p.endswith(".py")
            elif c.get("type") == "tool_result" and c.get("tool_use_id") in uses:
                name, inp = uses[c["tool_use_id"]]
                out, cmd = text_of(c.get("content", "")), inp.get("command", "")
                if name != "Bash":
                    continue
                if m["first"] is None:
                    m["first"] = {"cmd": cmd, "got": out.splitlines()[:3]}
                session.append("$ %s\n%s" % (cmd, "\n".join(out.splitlines()[:60])))
                if c["tool_use_id"] in denied or not SA_CMD.search(cmd):
                    continue
                m["sa_cmds"] += 1
                m["piped"] += bool(re.search(r"[|>]", cmd))
    reply = final.get("result") or ""
    fr = reply.split("FRICTION:", 1)
    m.update(reply=reply, friction=fr[1].strip() if len(fr) > 1 else "",
             cost=final.get("total_cost_usd", 0), turns=final.get("num_turns", 0),
             secs=round(final.get("duration_ms", 0) / 1000))
    return m, "\n\n".join(session)[-30000:]


def truth_of(task, bin_, cwd):
    return "\n\n".join("$ %s\n%s" % (c, (r.stdout + r.stderr).strip())
                       for c in task["truth"] for r in [sh(c, bin_, cwd, 600)])


def grade(persona, task, m, session, truth, args, bin_, cwd):
    prompt = (EVALS / "grader_prompt.md").read_text().format(
        id=task["id"], persona=persona, principles=task["principles"],
        question=task["question"], note=task.get("note", ""), truth=truth[:40000],
        session=session, answer=m["reply"][-8000:])
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--tools", ""] + ISOLATE
    r = sh(cmd + ["--model", args.grader_model], bin_, cwd, 900)
    try:
        res = json.loads(r.stdout)
        text = res.get("result", "")
        g = json.JSONDecoder().raw_decode(text[text.index("{"):])[0]
        g["cost"] = res.get("total_cost_usd", 0)
        return g
    except (ValueError, KeyError) as exc:
        return {"verdict": "ungraded", "why": "grader output unparsable: %s" % exc,
                "findings": [], "raw": r.stdout[-2000:]}


def run_group(group, args, bin_, src, tmp, out, truths):
    """One agent session over the group's journeys, in order, in one cwd."""
    session = str(uuid.uuid4()) if len(group) > 1 else None
    cwd = tmp / "work" / ("%s-%s-r%d" % (group[0][0], group[0][1]["id"], group[0][2]))
    cwd.mkdir(parents=True)
    ms, spent = [], 0.0
    for i, (p, t, n) in enumerate(group):
        ms.append(run_one(p, t, n, args, bin_, src, out, truths, cwd, session, i))
        ms[-1]["cost"], spent = ms[-1]["cost"] - spent, ms[-1]["cost"]  # a resumed run reports the session's
    return ms


def run_one(persona, task, n, args, bin_, src, out, truths, cwd, session, at):
    tag = "%s-%s-r%d" % (persona, task["id"], n)
    log = out / (tag + ".sa.jsonl")
    r = sh(agent_cmd(persona, task, args, session, at > 0), bin_, cwd, 1800, log)
    (out / (tag + ".jsonl")).write_text(r.stdout)
    events = [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]
    m, session = measure(events, src, log)
    g = grade(persona, task, m, session, truths[task["id"]], args, bin_, cwd)
    (out / (tag + ".grade.json")).write_text(json.dumps(g, indent=1))
    m.update(verdict=g.get("verdict", "ungraded"), grade=g, persona=persona, run=n,
             journey=task["id"], principles=task["principles"], turn=at + 1 if session else 0)
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--label", required=True)
    ap.add_argument("--personas", default="hurried,scientific")
    ap.add_argument("--tasks", help="ids, comma-separated (named held-out ones run)")
    ap.add_argument("--include-held-out", action="store_true")
    ap.add_argument("--days", type=int, default=7, help="snapshot: last N days")
    ap.add_argument("--rev", help="run sa from a worktree of REV")
    ap.add_argument("--baseline", help="a previous run dir")
    ap.add_argument("--model", help="agent model")
    ap.add_argument("--grader-model", default="sonnet", help="grader model (default sonnet)")
    ap.add_argument("--fresh", action="store_true", help="a fresh agent per journey, no session")
    ap.add_argument("--budget", type=float, default=2.0, help="max USD per agent run")
    ap.add_argument("--repeat", type=int, default=1, help="runs per cell")
    ap.add_argument("--jobs", type=int, default=3, choices=(1, 2, 3))
    ap.add_argument("--keep", action="store_true", help="keep temp dir")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    groups = load_tasks(args)
    if not groups:
        sys.exit("no (persona, journey) selected")
    out = EVALS / "runs" / ("%s-%s" % (datetime.date.today(), args.label))
    base = None
    if args.baseline:
        base = json.loads((Path(args.baseline) / "results.json").read_text())["results"]
    if out.exists() and not args.dry_run:
        sys.exit("%s exists: pick another --label" % out)
    tmp = Path(tempfile.mkdtemp(prefix="sa-eval-"))
    src, bin_, files = setup(tmp, args)
    print("temp dir %s: snapshot %d files, sa from %s" % (tmp, files, src))
    try:
        if args.dry_run:
            print(sh("sa -h", bin_, tmp).stdout.splitlines()[0])
            for group in groups:
                session = "<uuid>" if len(group) > 1 else None
                for i, (p, t, n) in enumerate(group):
                    print("\n# %s/%s r%d %s (PATH=%s:..., SA_LOG=<run>.sa.jsonl)" % (
                        p, t["id"], n, "session turn %d" % (i + 1) if session else "cold", bin_))
                    print(" ".join(shlex.quote(c) for c in agent_cmd(p, t, args, session, i > 0)))
            return
        out.mkdir(parents=True)
        truths = {t["id"]: truth_of(t, bin_, tmp) for g in groups for _, t, _ in g}
        (out / "truth.json").write_text(json.dumps(truths, indent=1))
        with cf.ThreadPoolExecutor(args.jobs) as pool:
            results = [m for ms in pool.map(lambda g: run_group(g, args, bin_, src, tmp, out, truths), groups)
                       for m in ms]
        rev = subprocess.run(["git", "rev-parse", "--short", args.rev or "HEAD"], cwd=REPO,
                             capture_output=True, text=True).stdout.strip()
        meta = dict(label=args.label, rev=rev + ("" if args.rev else "+tree"), files=files,
                    days=args.days, model=args.model or "default",
                    grader=args.grader_model)
        (out / "results.json").write_text(json.dumps({"meta": meta, "results": results}, indent=1))
        (out / "scorecard.md").write_text(scorecard(results, meta, base))
        print("wrote %s/scorecard.md; agents $%.2f, grader $%.2f" % (
            out, sum(r["cost"] for r in results),
            sum(r["grade"].get("cost", 0) for r in results)))
    finally:
        if args.keep:
            print("kept %s" % tmp)
        else:
            if args.rev:
                subprocess.run(["git", "worktree", "remove", "--force", str(src)], cwd=REPO)
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
