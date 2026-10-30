# -*- coding: utf-8 -*-
"""Summary slide for the Delft3D User Days 2026 deck, as a configuration lineage.

The slide carries a top-down genealogy of the model configurations. The spine
holds the line that leads to the setup in use, from the lagoon-only
hydrodynamic model of 2025 through the version sequence v01 to v04AE and on to
the vegetation module and the stratified initial state. The outlined boxes on
the right of each row are branches that were run and left outside that line.

Every label is sourced. The 2025 rows come from the speech of the 2025
presentation in docs/dsd2026/PresentationDelft2025.docx and from
oldModel/Stagnone_justLagoon/3d_lagoon_mann_variable.mdu, which carries five
sigma layers, Manning 0.02 and a friction field with eight polygon classes. The
version rows come from the history table of README.md and from the model
directories. The branch rows come from the memory entries on the trachytope
momentum sink, on the mobile bed under wave coupling and on the mesh and layer
convergence tests.

The input deck is not modified. The slide is inserted before the
acknowledgements slide of a copy, and the footer number of that slide moves on
by one.

Usage:
    python scripts/build_dsd2026_lineage_slide.py
    python scripts/build_dsd2026_lineage_slide.py --in <deck> --out <deck>
"""
from pathlib import Path
import argparse
import copy
import shutil

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
DECK_IN = ROOT / "docs" / "dsd2026" / "dsd2026_cmj_vf.pptx"
DECK_OUT = ROOT / "docs" / "dsd2026" / "dsd2026_cmj_vf_lineage.pptx"

# palette read off the deck
INK = RGBColor(0x0D, 0x21, 0x37)
BODY = RGBColor(0x33, 0x45, 0x55)
MUTED = RGBColor(0x6B, 0x7D, 0x8C)
FAINT = RGBColor(0x8A, 0x9B, 0xB0)
CARD = RGBColor(0xEF, 0xF4, 0xF8)
EDGE = RGBColor(0xDA, 0xE5, 0xED)
SPINE = RGBColor(0xB8, 0xCB, 0xDA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE = RGBColor(0x1A, 0x6B, 0x8A)
GREEN = RGBColor(0x2E, 0x8B, 0x61)

TITLE = "Lineage of the model configurations"
SUBTITLE = ("From the lagoon-only hydrodynamic model of 2025 to the configuration now in use. "
            "The outlined boxes were tested and left outside that line.")

# tag, title, detail, era colour key
SPINE_ROWS = [
    ("2025", "Lagoon-only hydrodynamics",
     "Five sigma layers, water level at the two inlets, wind from one station", "past"),
    ("2025", "Bed roughness as the calibration",
     "Uniform Manning at 0.02, 0.04 and 0.06, then a map by meadow class", "past"),
    ("v01", "Domain extended to the open sea",
     "25,212 faces, CMEMS levels and profiles, ten sigma layers", "line"),
    ("v02", "Blended wind and a boundary datum",
     "ERA5 merged with the in-situ stations, uniform offset of +0.42 m", "line"),
    ("v03", "Waves, tracers and a hypersaline state",
     "SWAN nested grids through DIMR, initial salinity at 42 psu", "line"),
    ("v03d", "Wave coupling repaired",
     "Classic NetCDF for the exchange file, duplicate tide boundary removed", "line"),
    ("v04", "Offset per boundary node, evaporation",
     "Anchored on the Marettimo record, ERA5 evaporation holds the salinity", "line"),
    ("v04AE", "Wind blend reduced to one station",
     "ERA5 with the AE gauge alone, a 36 degree direction bias removed", "line"),
    ("veg", "Canopy through the [veg] module",
     "Drag per layer, canopy height 0.40 m, no parameter fitted", "now"),
    ("ic3d", "Stratified initial state",
     "CMEMS profiles at the start time, the configuration in use", "now"),
]

# row index, title, detail, status, status colour key
BRANCH_ROWS = [
    (1, "Depth-averaged comparison",
     "The same roughness map in two dimensions, damped oscillation",
     "reference", "faint"),
    (4, "HDF5 isolation tests",
     "Five configurations to find why the wave field froze",
     "diagnosed", "faint"),
    (6, "Mobile bed, D-Morph",
     "Two fractions, suspended load at 9 g/l under wave coupling",
     "kept off", "faint"),
    (7, "Wind blend variants",
     "Raw ERA5, and the three-station blend at 0.16 lower skill",
     "superseded", "faint"),
    (8, "Baptist trachytopes",
     "Canopy as bed friction only, the momentum sink is not read",
     "superseded", "faint"),
    (9, "Mesh and layer convergence",
     "60 to 15 m and five to forty layers, skill within 0.005",
     "no change", "faint"),
]

CARDS = [
    ("Roughness as a proxy for the canopy",
     "Uniform and variable Manning changed the velocity profile and left the water level "
     "unchanged. The same meadow as bed friction raises the bed shear stress by half, where "
     "the canopy drag lowers it by a factor of eleven."),
    ("Forcing and datum before parameters",
     "Extending the domain to the open sea, anchoring the datum on the Marettimo record and "
     "taking the wind from the lagoon station removed errors that bed roughness had been "
     "absorbing."),
    ("Lagrangian skill as the discriminator",
     "Anomaly RMSE at the three gauges stays between 2 and 4 cm along the whole lineage, "
     "while the drifter skill separates the configurations, 0.619 bare against 0.739 with "
     "the canopy."),
]

NOTES = """A summary of where the configuration came from, because the talk has
moved through a lot of separate pieces.

The spine on the left is the line that leads to the model I am running now. The
two grey rows at the top are what I presented here last year. A lagoon-only
domain, five sigma layers, water level prescribed at the two inlets and wind
from a single station. At that stage the calibration knob was the bed
roughness, and I swept uniform Manning at 0.02, 0.04 and 0.06 and then a map by
meadow class. The branch beside that row is the depth-averaged run I showed for
comparison, which damped the oscillation.

Then the domain was extended to the open sea, and that is the single change
that mattered most. The boundary moved off the inlets, the levels and the
profiles came from CMEMS, and the vertical went to ten layers. From there the
sequence is incremental. A blended wind field and a datum offset at the
boundary. Waves through SWAN and DIMR, with the hypersaline initial state and
the turbidity tracers. Then a repair, because the wave field was freezing
silently, and it took five isolation runs to find that SWAN could not re-open
the exchange file. Classic NetCDF fixed it, and the duplicate tide boundary
came out at the same time. Then the offset per boundary node anchored on the
Marettimo record, and evaporation from ERA5 so the salinity holds. Then the
wind, where cutting the blend back to the one gauge inside the lagoon removed a
36 degree direction bias on the eastern shore.

The last two rows are this year. The canopy through the vegetation module, and
the stratified initial state.

The outlined boxes are what was run and left outside the line. The mobile bed
is functional and stays off, because under wave coupling the suspended load
reaches nine grams per litre. The Baptist trachytopes were the first canopy,
and they act as bed friction only, since the momentum sink is not read, which
is why the vegetation module sits above them. The mesh and layer convergence
tests moved the skill by less than five thousandths, and that is what lets me
attribute the rest to the physics.

Two branches are not on the figure. The 2026 bathymetry from the survey boat
raises the skill by 0.016 inside the lagoon and is not usable outside it. The
continuation chain runs the first twenty days of July without restart shock,
and that one belongs to the maturity slide.

If there is one reading of the whole figure, it is the third card. The water
level anomaly is between two and four centimetres everywhere along this
lineage, including at the top, and it never told me which configuration was
better.
"""


def put_text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """Text box with one paragraph per (text, size, bold, colour) tuple."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, (text, size, bold, colour) in enumerate(runs):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        run = para.add_run()
        run.text = text
        run.font.name = "Calibri"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = colour
    return box


def put_box(slide, x, y, w, h, fill, line, radius=0.16):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    shape.adjustments[0] = radius
    shape.text_frame.text = ""
    return shape


def put_chip(slide, x, y, w, h, text, fill, size=8.5):
    chip = put_box(slide, x, y, w, h, fill, fill, radius=0.3)
    tf = chip.text_frame
    tf.word_wrap = False
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    run = para.add_run()
    run.text = text
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.font.bold = True
    run.font.color.rgb = WHITE
    return chip


def put_oval(slide, x, y, d, text, fill):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    shape.shadow.inherit = False
    tf = shape.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    run = para.add_run()
    run.text = text
    run.font.name = "Calibri"
    run.font.size = Pt(12)
    run.font.bold = True
    run.font.color.rgb = WHITE
    return shape


def put_line(slide, x1, y1, x2, y2, colour, width=1.0, dashed=False):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                      Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conn.line.color.rgb = colour
    conn.line.width = Pt(width)
    if dashed:
        try:
            from pptx.enum.dml import MSO_LINE_DASH_STYLE
            conn.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        except Exception:
            # the enum is absent in some builds, so the preset goes on the XML
            from lxml import etree
            from pptx.oxml.ns import qn
            ln = conn.line._get_or_add_ln()
            etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    return conn


def set_notes(prs, slide, text):
    """Write the speaker notes, borrowing a body placeholder when there is none.

    The notes master of this deck carries no body placeholder, so python-pptx
    builds a notes slide whose notes_text_frame is absent. The element is copied
    from a slide that already has notes and emptied before the text goes in.
    """
    notes = slide.notes_slide
    if notes.notes_text_frame is None:
        donor = None
        for other in prs.slides:
            if other is slide or not other.has_notes_slide:
                continue
            if other.notes_slide.notes_placeholder is not None:
                donor = other.notes_slide.notes_placeholder
                break
        if donor is None:
            raise SystemExit("no notes placeholder to copy from")
        element = copy.deepcopy(donor._element)
        notes.shapes._spTree.append(element)
    frame = notes.notes_text_frame
    frame.clear()
    frame.text = text


# geometry, in inches
ROW_Y0, ROW_PITCH, ROW_H = 1.74, 0.513, 0.42
TAG_X, TAG_W = 0.60, 0.62
NODE_X, NODE_W = 1.30, 4.05
BR_X, BR_W = 5.75, 3.40
COL_X, COL_W = 9.35, 3.38


def build_slide(prs, footer_text, footer_number):
    layout = next((l for l in prs.slide_layouts if l.name == "Blank"), prs.slide_layouts[6])
    slide = prs.slides.add_slide(layout)

    head = put_text(slide, 0.60, 0.36, 12.10, 0.62, [(TITLE, 28, True, INK)])
    head.text_frame.paragraphs[0].runs[0].font.name = "Cambria"
    put_text(slide, 0.60, 1.00, 11.60, 0.46, [(SUBTITLE, 12.5, False, MUTED)])
    put_text(slide, 0.60, 7.04, 10.60, 0.26, [(footer_text, 8.5, False, FAINT)])
    put_text(slide, 11.40, 7.04, 1.33, 0.26, [(footer_number, 8.5, False, FAINT)],
             align=PP_ALIGN.RIGHT)

    # the spine goes in first, so the tags cover it between the rows
    y_first = ROW_Y0 + ROW_H / 2
    y_last = ROW_Y0 + (len(SPINE_ROWS) - 1) * ROW_PITCH + ROW_H / 2
    put_line(slide, TAG_X + TAG_W / 2, y_first, TAG_X + TAG_W / 2, y_last, SPINE, 1.5)

    era_fill = {"past": FAINT, "line": BLUE, "now": GREEN}
    for i, (tag, head, detail, era) in enumerate(SPINE_ROWS):
        y = ROW_Y0 + i * ROW_PITCH
        put_chip(slide, TAG_X, y + 0.02, TAG_W, ROW_H - 0.04, tag, era_fill[era])
        put_box(slide, NODE_X, y, NODE_W, ROW_H, CARD, EDGE)
        put_text(slide, NODE_X + 0.14, y + 0.055, NODE_W - 0.28, ROW_H - 0.09,
                 [(head, 9, True, INK), (detail, 7.5, False, BODY)])

    status_fill = {"faint": FAINT, "blue": BLUE}
    for row, head, detail, status, key in BRANCH_ROWS:
        y = ROW_Y0 + row * ROW_PITCH
        put_line(slide, NODE_X + NODE_W, y + ROW_H / 2, BR_X, y + ROW_H / 2,
                 SPINE, 1.0, dashed=True)
        put_box(slide, BR_X, y, BR_W, ROW_H, WHITE, EDGE)
        # the status chip sits on the title line, so the detail keeps the full width
        put_text(slide, BR_X + 0.14, y + 0.055, BR_W - 1.26, 0.17,
                 [(head, 9, True, MUTED)])
        put_text(slide, BR_X + 0.14, y + 0.225, BR_W - 0.28, 0.17,
                 [(detail, 7.5, False, MUTED)])
        put_chip(slide, BR_X + BR_W - 0.92, y + 0.07, 0.80, 0.21, status,
                 status_fill[key], size=6.5)

    for i, (head, body) in enumerate(CARDS):
        y = 1.74 + i * 1.68
        put_box(slide, COL_X, y, COL_W, 1.58, CARD, EDGE)
        put_oval(slide, COL_X + 0.22, y + 0.18, 0.40, str(i + 1), BLUE)
        put_text(slide, COL_X + 0.77, y + 0.15, COL_W - 0.99, 0.42,
                 [(head, 11.5, True, INK)])
        put_text(slide, COL_X + 0.22, y + 0.60, COL_W - 0.44, 0.92,
                 [(body, 9.5, False, BODY)])

    set_notes(prs, slide, NOTES)
    return slide


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", type=Path, default=DECK_IN)
    ap.add_argument("--out", dest="dst", type=Path, default=DECK_OUT)
    args = ap.parse_args()

    shutil.copy2(args.src, args.dst)
    prs = Presentation(str(args.dst))

    # the acknowledgements slide is the anchor, and its footer number moves on by one
    ack_index, footer_text, footer_box = None, None, None
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if text.lower().startswith("acknowledg"):
                ack_index = i
            if "WETWISE" in text and "Delft3D User Days" in text:
                footer_text = text
            if ack_index == i and text.isdigit():
                footer_box = shape
    if ack_index is None:
        raise SystemExit("no acknowledgements slide found")
    number = footer_box.text_frame.text.strip() if footer_box is not None else "17"
    print(f"acknowledgements at slide {ack_index + 1}, footer {number}")

    build_slide(prs, footer_text, number)

    ids = prs.slides._sldIdLst
    added = list(ids)[-1]
    ids.remove(added)
    ids.insert(ack_index, added)

    if footer_box is not None:
        footer_box.text_frame.paragraphs[0].runs[0].text = str(int(number) + 1)

    prs.save(str(args.dst))
    print(f"wrote {args.dst}  ({args.dst.stat().st_size / 1e6:.1f} MB, "
          f"{len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
