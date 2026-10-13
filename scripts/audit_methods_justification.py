"""Flag parameter statements in the Methods that carry no stated ground.

The internal review of Paper 1 returned the same criticism twice in its first
five items: a value is given and the reason for it is not. Scanning for the
pattern by eye misses cases, so this does it by rule.

A sentence is flagged when it asserts a setting, meaning a number with a unit,
a named formulation, or a switch, and neither it nor its immediate neighbour
carries a ground. A ground is a causal or purposive clause, a reference to a
constraint the choice answers, or a citation, on the view that citing the
source of a formulation is itself the reason for using it.

The output is a list of candidates, not a verdict. A sentence can be properly
grounded by a paragraph two sentences away, which this does not see, and a
sentence can carry a ground that is weak, which this cannot judge.
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / 'manuscript' / 'sections'

# A value asserted: a number with a unit or a bare numeric setting, a named
# scheme, or a switch being set.
VALUE = re.compile(
    r'\d+(?:[.,]\d+)?\s*(?:~)?\\?si\{|'          # siunitx
    r'\d+(?:[.,]\d+)?\s*~?(?:m|s|h|Hz|ppt|km|%|\\%)\b|'
    r'\$?\\?(?:alpha|gamma|times)\s*=|'
    r'\b\d+(?:[.,]\d+)?\s*(?:layers|partitions|directions|frequencies|'
    r'nodes|faces|fractions|cells|days)\b|'
    r'\\texttt\{[^}]*\}\s*(?:=|\d)|'
    r'\b(?:set to|fixed at|held at|imposed|prescribed as|disabled|enabled|'
    r'active|were used|was used|followed the)\b')

# A ground offered: cause, purpose, the constraint answered, or a citation.
GROUND = re.compile(
    r'\b(?:because|since|so that|so as to|in order to|to avoid|to prevent|'
    r'to permit|to allow|to keep|which was required|was required|is required|'
    r'required for|necessary for|appropriate to|consistent with|following|'
    r'after|given that|as the|reflects|chosen|selected|on the grounds|'
    r'otherwise|else the|would)\b|'
    r'\\cite[tp]?\{|'
    r'\bwhich (?:distributes|retains|leaves|removes|resolves|gives|makes)\b')

SENT = re.compile(r'(?<=[.;])\s+(?=[A-Z\\$])')


def sentences(tex):
    body = '\n'.join(l for l in tex.splitlines()
                     if not l.strip().startswith('%'))
    body = re.sub(r'\\begin\{(figure|table|tabular)\}.*?\\end\{\1\}', ' ',
                  body, flags=re.S)
    body = re.sub(r'\\(?:sub)*section\{[^}]*\}|\\label\{[^}]*\}', ' ', body)
    body = re.sub(r'\s+', ' ', body)
    return [s.strip() for s in SENT.split(body) if len(s.strip()) > 25]


def audit(path):
    sents = sentences(path.read_text(encoding='utf-8'))
    flagged = []
    for i, s in enumerate(sents):
        if not VALUE.search(s):
            continue
        window = ' '.join(sents[max(0, i - 1):i + 2])
        if GROUND.search(window):
            continue
        flagged.append(s)
    return sents, flagged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*',
                    help='section .tex files; default is 03_data_methods.tex')
    a = ap.parse_args()
    paths = ([Path(f) for f in a.files]
             or [SECTIONS / '03_data_methods.tex'])

    total_s = total_f = 0
    for p in paths:
        sents, flagged = audit(p)
        total_s += len(sents)
        total_f += len(flagged)
        print(f'\n===== {p.name}: {len(flagged)} of {len(sents)} sentences '
              f'assert a setting with no ground nearby =====')
        for s in flagged:
            s = re.sub(r'\\si\{([^}]*)\}', r'[\1]', s)
            s = re.sub(r'\\texttt\{([^}]*)\}', r'`\1`', s)
            s = re.sub(r'[{}$\\]', '', s)
            print(f'  - {s[:200]}')
    print(f'\n{total_f} flagged across {total_s} sentences')


if __name__ == '__main__':
    main()
