"""The scorecard of an agent eval run (``scripts/agent_eval.py``): per
persona a table of measures per journey, findings by principle, verdicts and
friction, and with ``--baseline`` the measures that got worse. Never one score."""

MEASURES = ["verdict", "sa_cmds", "error_exits", "denied", "source_reads",
            "max_lines", "gates"]
PAIRED = {"verdict": "sa_cmds", "sa_cmds": "verdict", "error_exits": "sa_cmds",
          "denied": "sa_cmds", "source_reads": "verdict", "max_lines": "sa_cmds",
          "gates": "verdict"}
RANK = {"correct": 0, "partial": 1, "wrong": 2, "no_answer": 3}


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
                r["journey"], "%d%s" % (r["run"], " s%d" % r["turn"] if r.get("turn") else " cold"), r["verdict"],
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
