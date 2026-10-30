# -*- coding: utf-8 -*-
"""Make the footer numbers of the deck continuous, and give the new slide its notes.

Two slides left the deck in the manual revision of 30 October, so the footer
sequence runs 11, 11, 14 and the audience sees two slides numbered 11 followed
by a jump of two. The Valletta long-wave slide comes from another template and
carries no number at all. The turbidity slide was built by duplicating the one
before it and still holds that slide's speaker notes.

Numbers follow what the deck shows rather than how many frames it holds, so the
slides that exist as animation steps of the same number keep sharing it.

Usage:
    python scripts/fix_dsd2026_slide_numbers.py
    python scripts/fix_dsd2026_slide_numbers.py --deck <deck>
"""
from pathlib import Path
import argparse

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "docs" / "dsd2026" / "dsd2026_cmj_vf_lineage_light.pptx"

FAINT = RGBColor(0x8A, 0x9B, 0xB0)

# a fragment of the slide title, and the number its footer should carry
NUMBERING = [
    ("Turbidity", "12"),
    ("Execution on HPC", "13"),
    ("Digital twin maturity", "14"),
    ("Transfer to Valletta", "15"),
    ("amplify long waves", "16"),
    ("Lineage of the model", "17"),
    ("Acknowledg", "18"),
]

TURBIDITY_NOTES = """The next question is open, and it is the one the lagoon community asks first.

Two channels discharge into this coast. One drains the Birgi airport catchment,
the other the Trapani salt pans. PlanetScope catches the plume directly. These
are scenes from late March this year, and the sediment leaves the channel mouth
and turns south along the shore, towards the lagoon.

The model carries two passive tracers released at those two points, and on the
right is what it does with them over three days of July. The plume leaves the
coast within a day, and the lagoon holds it after the open coast has cleared.
That retention contrast is the part I trust.

What I do not yet have is a discharge. The animation is the transport of a
released patch, not a time series of concentration, because the lateral inflow
carries water into the domain without carrying a concentration with it. Until
that is fixed, this stays a research question and not a result.

Technical note, not for the floor. The [Lateral] block is accepted and carries
water, but the concentration depends on a tracerbnd over a one-point polyline,
which the kernel opens with zero cells. The correct injection is
discharge_salinity_temperature_sorsin in the legacy .ext. The tracer field also
diverges from 4 to 5 July, which is why the window stops on the fourth.
"""


def title_of(slide):
    """Every line of text in the title band, joined.

    The Valletta slide comes from another template and carries two headings at
    the top, so the first one found is not reliably the one that names it.
    """
    parts = []
    for shape in slide.shapes:
        if shape.has_text_frame and shape.top is not None and shape.top < Inches(0.9):
            text = shape.text_frame.text.strip()
            if text:
                parts.append(text)
    return " | ".join(parts)


def number_box(slide):
    """The footer number box, recognised by its position and short digit text."""
    for shape in slide.shapes:
        if not shape.has_text_frame or shape.top is None:
            continue
        if shape.top > Inches(6.9) and shape.text_frame.text.strip().isdigit():
            return shape
    return None


def set_number(slide, value):
    box = number_box(slide)
    if box is None:
        box = slide.shapes.add_textbox(Inches(11.40), Inches(7.04), Inches(1.33), Inches(0.26))
        frame = box.text_frame
        frame.word_wrap = False
        frame.margin_left = frame.margin_right = 0
        frame.margin_top = frame.margin_bottom = 0
        para = frame.paragraphs[0]
        para.alignment = PP_ALIGN.RIGHT
        run = para.add_run()
        run.font.name = "Calibri"
        run.font.size = Pt(8.5)
        run.font.color.rgb = FAINT
        run.text = value
        return "added"
    para = box.text_frame.paragraphs[0]
    before = para.runs[0].text
    para.runs[0].text = value
    for extra in para.runs[1:]:
        extra.text = ""
    return f"{before} -> {value}" if before != value else "kept"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", type=Path, default=DECK)
    args = ap.parse_args()

    prs = Presentation(str(args.deck))
    slides = list(prs.slides)

    for fragment, value in NUMBERING:
        hits = [(i, s) for i, s in enumerate(slides, 1) if fragment in title_of(s)]
        if not hits:
            raise SystemExit(f"no slide titled with {fragment!r}")
        for index, slide in hits:
            print(f"  slide {index:>2}  {title_of(slide)[:44]:<44} {set_number(slide, value)}")

    turbid = [s for s in slides if "Turbidity" in title_of(s)]
    frame = turbid[0].notes_slide.notes_text_frame
    frame.clear()
    frame.text = TURBIDITY_NOTES
    print("  notes of the turbidity slide replaced")

    prs.save(str(args.deck))
    print(f"saved {args.deck}  ({args.deck.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
