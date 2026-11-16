"""session-analyzer v2: what did it cost, and, cost aside, where did my context go.

Read Claude Code transcripts (``corpus``), cut them into context windows
(``windows``), turn each window into facts (``walk``, ``heads``), select and
reconcile them (``query``, ``reconciliation``), and print them (``cli`` reads
the words with ``grammar``; ``render`` lays out ``headline``, ``tables``,
``leaves``, ``notes`` and ``checks``; ``style`` paints). ``schema`` is the one
table the others read; ``glossary`` its words; ``usage`` holds the measured
helpers; ``sweep`` measures the figures the docstrings cite.
"""
__version__ = "2.0.0"  # the one place: pyproject.toml and the plugin manifests read or match it
