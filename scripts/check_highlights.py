r"""Verify the ECSS highlights against the Guide for Authors limits.

The guide requires 3 to 5 bullet points, each a maximum of 85 characters
including spaces. Character counts are easy to get wrong by eye, and a bullet
that overruns is rejected at the submission-system level rather than in review,
so check it mechanically. LaTeX escapes are unescaped before counting, since
'30\%' is three characters on the page, not four.
"""
import re
import sys
from pathlib import Path

LIMIT = 85
SRC = Path(__file__).resolve().parents[1] / 'manuscript' / 'highlights.tex'


def main():
    body = SRC.read_text(encoding='utf-8')
    body = body.split(r'\begin{itemize}')[1].split(r'\end{itemize}')[0]
    # split() puts the itemize optional arguments in the first chunk, before
    # any \item, so drop it rather than counting it as a bullet
    items = [b.strip() for b in body.split(r'\item')[1:] if b.strip()]

    ok = True
    if not 3 <= len(items) <= 5:
        print(f'FAIL  {len(items)} bullets, the guide allows 3 to 5')
        ok = False

    for i, raw in enumerate(items, 1):
        t = re.sub(r'\\%', '%', raw)
        t = re.sub(r'\\emph\{([^}]*)\}', r'\1', t)
        t = re.sub(r'\s+', ' ', t).strip().rstrip(',')
        n = len(t)
        flag = 'ok  ' if n <= LIMIT else 'OVER'
        if n > LIMIT:
            ok = False
        print(f'{flag} {i}  {n:3d}/{LIMIT}  {t}')

    print('\nPASS' if ok else '\nFAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
