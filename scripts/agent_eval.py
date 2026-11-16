"""Can a cold agent learn and use `sa` from its own output alone?

Each (persona, journey) of evals/tasks.json runs as `claude -p` in a temp dir
outside the repo (Bash(python3 -m sa ...) and Read, a frozen snapshot); the
wrapper logs what the CLI printed; a second `claude -p` grades the answer.
Per journey and principle, never one score. See evals/README.md.
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
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVALS = REPO / "evals"
SA_CMD = re.compile(r"^\s*(sa|python3 -m sa)(\s|$)")
ISOLATE = ["--setting-sources", "", "--strict-mcp-config",
           "--disable-slash-commands", "--no-session-persistence"]
MEASURES = ["verdict", "sa_cmds", "error_exits", "denied", "source_reads",
            "max_lines", "gates"]
PAIRED = {"verdict": "sa_cmds", "sa_cmds": "verdict", "error_exits": "sa_cmds",
          "denied": "sa_cmds", "source_reads": "verdict", "max_lines": "sa_cmds",
          "gates": "verdict"}
RANK = {"correct": 0, "partial": 1, "wrong": 2, "no_answer": 3}


def load_tasks(args):
    tasks = json.loads((EVALS / "tasks.json").read_text())["tasks"]
    want = set(args.tasks.split(",")) if args.tasks else None
    jobs = []
    for t in tasks:
        if want is not None and t["id"] not in want:
            continue
        if t.get("held_out") and not (args.include_held_out or want):
            continue
        jobs += [(p, t, n) for p in t["personas"] if p in args.personas.split(",")
                 for n in range(1, args.repeat + 1)]
    return jobs


def setup(tmp, args):
    snap, src, bin_ = tmp / "corpus", tmp / "src", tmp / "bin"
    cutoff = time.time() - args.days * 86400
    home = Path.home() / ".claude" / "projects"
    for f in home.rglob("*"):
        if f.is_file() and f.stat().st_mtime >= cutoff:
            (snap / f.relative_to(home)).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, snap / f.relative_to(home))
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


def agent_cmd(persona, task, args):
    prompt = (EVALS / "agent_prompt.md").read_text().format(
        persona=(EVALS / "personas" / (persona + ".md")).read_text().strip(),
        question=task["question"])
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--tools", "Bash,Read", "--allowedTools", "Bash(python3 -m sa)", "Bash(python3 -m sa *)", "Read",
           "--permission-mode", "dontAsk", "--max-budget-usd", str(args.budget)]
    return cmd + ISOLATE + (["--model", args.model] if args.model else [])


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
        content = (e.get("message") or {}).get("content")
        for c in content if isinstance(content, list) else []:
            if c.get("type") == "tool_use":
                uses[c["id"]] = (c["name"], c.get("input", {}))
                if c["name"] == "Read":
                    p = c["input"].get("file_path", "")
                    m["reads"].append(p)
                    m["source_reads"] += p.startswith(str(src)) and "/sa/" in p
            elif c.get("type") == "tool_result" and c.get("tool_use_id") in uses:
                name, inp = uses[c["tool_use_id"]]
                out, cmd = text_of(c.get("content", "")), inp.get("command", "")
                if name != "Bash":
                    continue
                if m["first"] is None:
                    m["first"] = {"cmd": cmd, "got": out.splitlines()[:3]}
                session.append("$ %s\n%s" % (cmd, "\n".join(out.splitlines()[:60])))
                if c["tool_use_id"] in denied or not SA_CMD.match(cmd):
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
    r = sh(cmd + (["--model", args.grader_model] if args.grader_model else []),
           bin_, cwd, 900)
    try:
        res = json.loads(r.stdout)
        text = res.get("result", "")
        g = json.loads(text[text.index("{"):text.rindex("}") + 1])
        g["cost"] = res.get("total_cost_usd", 0)
        return g
    except (ValueError, KeyError) as exc:
        return {"verdict": "ungraded", "why": "grader output unparsable: %s" % exc,
                "findings": [], "raw": r.stdout[-2000:]}


def run_one(persona, task, n, args, bin_, src, tmp, out, truths):
    tag = "%s-%s-r%d" % (persona, task["id"], n)
    cwd, log = tmp / "work" / tag, out / (tag + ".sa.jsonl")
    cwd.mkdir(parents=True)
    r = sh(agent_cmd(persona, task, args), bin_, cwd, 1800, log)
    (out / (tag + ".jsonl")).write_text(r.stdout)
    events = [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]
    m, session = measure(events, src, log)
    g = grade(persona, task, m, session, truths[task["id"]], args, bin_, cwd)
    (out / (tag + ".grade.json")).write_text(json.dumps(g, indent=1))
    m.update(verdict=g.get("verdict", "ungraded"), grade=g, persona=persona, run=n,
             journey=task["id"], principles=task["principles"])
    return m


def cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def scorecard(results, meta, base):
    L = ["# Agent eval: %s" % meta["label"], "",
         "rev `%s`, snapshot %d files (%d days), model %s, grader %s. No aggregate "
         "score by design (UX_PRINCIPLES)." % (meta["rev"], meta["files"], meta["days"],
                                                 meta["model"], meta["grader"]), ""]
    for p in sorted({r["persona"] for r in results}):
        L += ["## %s" % p.upper(), "",
              "| journey | run | verdict | first command → got | sa cmds | piped by agent | "
              "error exits | denied | source reads | max lines printed | max width | "
              "gate fails | turns | s | $ |", "|---" * 15 + "|"]
        for r in (x for x in results if x["persona"] == p):
            f = r["first"] or {"cmd": "-", "got": []}
            L.append("| " + " | ".join(cell(v) for v in (
                r["journey"], r["run"], r["verdict"],
                "`%s` → %s" % (f["cmd"], " / ".join(f["got"])[:90]), r["sa_cmds"],
                r["piped"], r["error_exits"], r["denied"], r["source_reads"],
                r["max_lines"], r["max_width"], len(r["gates"]), r["turns"], r["secs"],
                "%.2f" % r["cost"])) + " |")
        L.append("")
    L += ["## Findings by principle", ""]
    for n, name in ((1, "Learnable"), (2, "Legible"), (3, "Trustworthy")):
        L += ["### %d. %s" % (n, name), ""]
        for r in results:
            for f in r["grade"].get("findings", []):
                if str(f.get("principle")) == str(n):
                    L.append("- %s/%s r%d: %s «%s»" % (r["persona"], r["journey"], r["run"],
                                                  f.get("finding"), cell(f.get("quote"))))
        L.append("")
    L += ["## Verdicts, friction, source reads, gates", ""]
    for r in results:
        g = r["grade"]
        L += ["**%s/%s r%d** %s: %s «%s»" % (r["persona"], r["journey"], r["run"], r["verdict"],
                                          g.get("why", ""), cell(g.get("quote", ""))),
              "- friction: %s" % cell(r["friction"] or "none")]
        if r["source_reads"]:
            L.append("- read source (%s): %s" % (r["journey"], ", ".join(r["reads"])))
        L += ["- GATE: %s" % cell(x) for x in r["gates"]] + [""]
    if base is not None:
        L += diff(results, base)
    return "\n".join(L) + "\n"


def worse(k, old, new):
    if k == "verdict":
        return RANK.get(new, 9) > RANK.get(old, 9)
    return len(new or []) > len(old or []) if k == "gates" else (new or 0) > (old or 0)


def diff(results, base):
    old = {(b["persona"], b["journey"], b.get("run", 1)): b for b in base}
    L = ["## Regressions vs baseline", "",
         "| persona/journey | measure | was → now | paired: was → now |", "|---|---|---|---|"]
    for r in results:
        b = old.get((r["persona"], r["journey"], r["run"]))
        for k in MEASURES if b else []:
            if worse(k, b.get(k), r.get(k)):
                q = PAIRED[k]
                L.append("| %s/%s r%d | %s | %s → %s | %s: %s → %s |" % (
                    r["persona"], r["journey"], r["run"], k, b.get(k), r.get(k), q, b.get(q), r.get(q)))
    return L + ["", "(rows only where a measure got worse; new journeys have no row)", ""]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--label", required=True)
    ap.add_argument("--personas", default="hurried,scientific")
    ap.add_argument("--tasks", help="ids, comma-separated (named held-out ones run)")
    ap.add_argument("--include-held-out", action="store_true")
    ap.add_argument("--days", type=int, default=7, help="snapshot: files modified in N days")
    ap.add_argument("--rev", help="run sa from a worktree of REV")
    ap.add_argument("--baseline", help="a previous run dir")
    ap.add_argument("--model", help="agent model (default: claude's)")
    ap.add_argument("--grader-model", help="grader model (default: claude's)")
    ap.add_argument("--budget", type=float, default=2.0, help="max USD per agent run")
    ap.add_argument("--repeat", type=int, default=1, help="runs per cell, side by side")
    ap.add_argument("--jobs", type=int, default=3, choices=(1, 2, 3))
    ap.add_argument("--keep", action="store_true", help="keep the temp dir")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    jobs = load_tasks(args)
    if not jobs:
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
            for p, t, n in jobs:
                print("\n# %s/%s r%d (PATH=%s:..., SA_LOG=<run>.sa.jsonl)" % (p, t["id"], n, bin_))
                print(" ".join(shlex.quote(c) for c in agent_cmd(p, t, args)))
            return
        out.mkdir(parents=True)
        truths = {t["id"]: truth_of(t, bin_, tmp) for _, t, _ in jobs}
        (out / "truth.json").write_text(json.dumps(truths, indent=1))
        with cf.ThreadPoolExecutor(args.jobs) as pool:
            results = list(pool.map(lambda j: run_one(*j, args, bin_, src, tmp, out, truths), jobs))
        rev = subprocess.run(["git", "rev-parse", "--short", args.rev or "HEAD"], cwd=REPO,
                             capture_output=True, text=True).stdout.strip()
        meta = dict(label=args.label, rev=rev + ("" if args.rev else "+tree"), files=files,
                    days=args.days, model=args.model or "default",
                    grader=args.grader_model or "default")
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
