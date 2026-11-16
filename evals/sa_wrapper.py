"""The `python3 -m sa` an eval agent runs: the real CLI on a frozen snapshot.

scripts/agent_eval.py copies this into the run's bin/ behind a `python3`
shim (and a `sa` used by the truth commands). It injects `--root SNAPSHOT`
wherever the CLI accepts it, learned from the CLI's own help so a grammar
change does not break the eval: after the subcommand if that subcommand's
help lists --root, else first if the top-level help does. Help requests pass
through untouched.

It measures what the CLI PRINTED, before any pipe the agent adds: when
SA_LOG is set it appends one JSON line per invocation (argv, exit, lines,
width, gate failures against the UX_PRINCIPLES budgets). The snapshot path
is shown as ~/.claude/projects, as the CLI prints the real root.
Env: SA_PY (real interpreter), SA_SRC (package dir), SA_ROOT (snapshot).
"""
import json
import os
import subprocess
import sys

PY, SRC, ROOT = os.environ["SA_PY"], os.environ["SA_SRC"], os.environ["SA_ROOT"]
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "root_flag.json")
ENV = dict(os.environ, PYTHONPATH=SRC)


def takes_root(sub):
    try:
        with open(CACHE) as f:
            known = json.load(f)
    except (OSError, ValueError):
        known = {}
    key = sub or ""
    if key not in known:
        out = subprocess.run([PY, "-m", "sa"] + ([sub] if sub else []) + ["-h"],
                             env=ENV, capture_output=True, text=True)
        known[key] = "--root" in out.stdout
        with open(CACHE, "w") as f:
            json.dump(known, f)
    return known[key]


def gates(args, code, lines):
    is_help = any(a in ("-h", "--help") for a in args)
    fails = ["line > 100 cols: %r" % l[:60] for l in lines if len(l) > 100][:1]
    if code and len(lines) > 2:
        fails.append("error is %d lines (> 2)" % len(lines))
    if is_help and len(lines) > 25:
        fails.append("-h is %d lines (> 25)" % len(lines))
    text = "\n".join(lines)
    if "MISMATCH" in text:
        fails.append("MISMATCH (accounting)")
    if code == 1 or "Traceback (most recent call last)" in text:
        fails.append("exit 1 / traceback")
    return fails


def main(args):
    asked = list(args)
    if args and not any(a in ("-h", "--help") or a.startswith("--root") for a in args):
        i = next((n for n, a in enumerate(args) if not a.startswith("-")), None)
        if i is not None and takes_root(args[i]):
            args = args[:i + 1] + ["--root", ROOT] + args[i + 1:]
        elif takes_root(None):
            args = ["--root", ROOT] + args
    r = subprocess.run([PY, "-m", "sa"] + args, env=ENV, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if os.environ.get("SA_LOG"):
        lines = (r.stdout + r.stderr).replace(ROOT, "~/.claude/projects").splitlines()
        rec = dict(argv=asked, exit=r.returncode, lines=len(lines),
                   width=max([len(l) for l in lines] or [0]),
                   gates=gates(asked, r.returncode, lines))
        with open(os.environ["SA_LOG"], "a") as f:
            f.write(json.dumps(rec) + "\n")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main(sys.argv[1:])
