"""session-analyzer v2: where did my context go, and what did it cost.

Read Claude Code transcripts (``corpus``), cut them into context windows
(``windows``), turn each window into facts (``walk``), and answer over the facts (``query``, ``render``, ``cli``). ``schema`` is
the one table the others read; ``usage`` holds the measured helpers.
"""
