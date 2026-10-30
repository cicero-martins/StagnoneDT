# -*- coding: utf-8 -*-
"""Cut the embedded videos of the Delft3D User Days deck to what the deck plays.

The seven MP4 parts account for 138 of the 164 MB the deck occupies, and most
of that is never shown. PowerPoint keeps the whole recording and stores the
played window as a `p14:trim` element beside the media relationship, so a part
of fifty-seven seconds can contribute five seconds to the talk. The screen
captures are also written by the recorder at 4.5 to 6.3 Mb/s, far above what a
mostly static user interface needs, and the four taken from Chrome carry an AAC
track at digital silence, measured at -91 dB.

Each part is cut to its played window, re-encoded at a constant quality factor
and stripped of the silent track. The trim element then goes, since the file
and the window coincide. A part shown twice through two different windows, as
the Valletta recording is, becomes two parts, and the second shape receives a
relationship of its own.

A part with no trim is played whole and is only re-encoded.

Usage:
    python scripts/compress_dsd2026_videos.py
    python scripts/compress_dsd2026_videos.py --crf 26 --in <deck> --out <deck>
"""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DECK_IN = ROOT / "docs" / "dsd2026" / "dsd2026_cmj_vf_lineage.pptx"
DECK_OUT = ROOT / "docs" / "dsd2026" / "dsd2026_cmj_vf_lineage_light.pptx"

MEDIA_REL = "http://schemas.microsoft.com/office/2007/relationships/media"
SLIDE_RE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
MEDIA_RE = re.compile(r'<p14:media\b[^>]*?r:embed="(rId\d+)"[^>]*?(?:/>|>(.*?)</p14:media>)', re.S)
TRIM_RE = re.compile(r"<p14:trim\b[^>]*/>")


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration_of(ff, path):
    out = subprocess.run([ff, "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", out)
    if not m:
        raise SystemExit(f"no duration for {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def encode(ff, src, dst, crf, window=None):
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    if window:
        cmd += ["-ss", f"{window[0]:.3f}", "-to", f"{window[1]:.3f}"]
    cmd += ["-i", str(src), "-an", "-c:v", "libx264", "-preset", "medium",
            "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(dst)]
    subprocess.run(cmd, check=True)


def window_of(inner, total):
    """The played window, from the trim that stores how much each end loses."""
    trim = TRIM_RE.search(inner or "")
    if not trim:
        return None
    start = re.search(r'st="([\d.]+)"', trim.group(0))
    end = re.search(r'end="([\d.]+)"', trim.group(0))
    a = float(start.group(1)) / 1000 if start else 0.0
    b = total - (float(end.group(1)) / 1000 if end else 0.0)
    if b - a < 0.2:
        print(f"    window {a:.2f} to {b:.2f} is empty, the part is kept whole")
        return None
    return (a, b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crf", type=int, default=23,
                    help="constant quality factor, lower keeps more detail")
    ap.add_argument("--in", dest="src", type=Path, default=DECK_IN)
    ap.add_argument("--out", dest="dst", type=Path, default=DECK_OUT)
    args = ap.parse_args()

    ff = ffmpeg_exe()
    work = Path(tempfile.mkdtemp(prefix="dsd_video_"))
    src_zip = zipfile.ZipFile(args.src)

    # every mp4 part, with the source bytes on disk and its total length
    parts = {}
    for name in sorted(n for n in src_zip.namelist()
                       if n.startswith("ppt/media/") and n.lower().endswith(".mp4")):
        raw = work / Path(name).name
        raw.write_bytes(src_zip.read(name))
        parts[name] = {"raw": raw, "dur": duration_of(ff, raw)}

    # the played window of every reference, slide by slide
    uses = []
    for name in src_zip.namelist():
        m = SLIDE_RE.match(name)
        if not m:
            continue
        xml = src_zip.read(name).decode("utf8")
        rels_name = f"ppt/slides/_rels/slide{m.group(1)}.xml.rels"
        rels = src_zip.read(rels_name).decode("utf8")
        rmap = dict(re.findall(r'Id="(rId\d+)"[^>]*?Target="([^"]+)"', rels))
        for order, hit in enumerate(MEDIA_RE.finditer(xml)):
            target = rmap.get(hit.group(1), "")
            part = "ppt/media/" + target.rsplit("/", 1)[-1]
            if part not in parts:
                continue
            uses.append({"slide": name, "rels": rels_name, "order": order,
                         "rid": hit.group(1), "part": part,
                         "window": window_of(hit.group(2), parts[part]["dur"])})

    # one output part per distinct window of a part, the first keeping the name
    taken = max(int(re.search(r"media(\d+)", n).group(1)) for n in parts)
    outputs, assigned = {}, {}
    for use in uses:
        key = (use["part"], use["window"])
        if key not in assigned:
            if not any(k[0] == use["part"] for k in assigned):
                target = use["part"]
            else:
                taken += 1
                target = f"ppt/media/media{taken}.mp4"
            assigned[key] = target
            outputs[target] = {"src": parts[use["part"]]["raw"], "window": use["window"]}
        use["target"] = assigned[key]

    print("encoding")
    blobs, before, after = {}, 0, 0
    for target, spec in outputs.items():
        dst = work / ("out_" + Path(target).name)
        encode(ff, spec["src"], dst, args.crf, spec["window"])
        blobs[target] = dst.read_bytes()
        src_size = spec["src"].stat().st_size
        win = (f"{spec['window'][0]:6.2f} to {spec['window'][1]:6.2f} s"
               if spec["window"] else "whole           ")
        print(f"  {Path(target).name:<12} {win}  {src_size/1e6:6.1f} -> "
              f"{len(blobs[target])/1e6:5.2f} MB", flush=True)
        after += len(blobs[target])
    before = sum(p["raw"].stat().st_size for p in parts.values())

    # the slide XML loses its trims, and a split part needs a relationship
    new_xml, new_rels = {}, {}
    for slide in sorted({u["slide"] for u in uses}):
        here = [u for u in uses if u["slide"] == slide]
        rels_name = here[0]["rels"]
        rels = new_rels.get(rels_name) or src_zip.read(rels_name).decode("utf8")
        rmap = dict(re.findall(r'Id="(rId\d+)"[^>]*?Target="([^"]+)"', rels))
        next_id = max(int(r[3:]) for r in rmap) + 1
        for use in here:
            want = "../media/" + Path(use["target"]).name
            if rmap.get(use["rid"]) == want:
                continue
            match = [r for r, t in rmap.items() if t == want and MEDIA_REL in rels]
            if match:
                use["rid"] = match[0]
                continue
            rid = f"rId{next_id}"
            next_id += 1
            rels = rels.replace(
                "</Relationships>",
                f'<Relationship Id="{rid}" Type="{MEDIA_REL}" Target="{want}"/>'
                "</Relationships>")
            rmap[rid] = want
            use["rid"] = rid
            print(f"  {Path(slide).name}: {rid} -> {Path(use['target']).name}")
        new_rels[rels_name] = rels

        xml = src_zip.read(slide).decode("utf8")
        order = {u["order"]: u for u in here}
        counter = [0]

        def swap(hit):
            i = counter[0]
            counter[0] += 1
            use = order.get(i)
            if use is None:
                return hit.group(0)
            text = hit.group(0)
            text = re.sub(r'r:embed="rId\d+"', f'r:embed="{use["rid"]}"', text, count=1)
            return TRIM_RE.sub("", text)

        new_xml[slide] = MEDIA_RE.sub(swap, xml)

    with zipfile.ZipFile(args.dst, "w", zipfile.ZIP_DEFLATED) as out_zip:
        written = set()
        for item in src_zip.infolist():
            if item.filename in blobs:
                data = blobs[item.filename]
            elif item.filename in new_xml:
                data = new_xml[item.filename].encode("utf8")
            elif item.filename in new_rels:
                data = new_rels[item.filename].encode("utf8")
            else:
                data = src_zip.read(item.filename)
            out_zip.writestr(item, data)
            written.add(item.filename)
        for target, data in blobs.items():
            if target not in written:
                out_zip.writestr(target, data)
    src_zip.close()
    shutil.rmtree(work, ignore_errors=True)

    print(f"video {before/1e6:.1f} -> {after/1e6:.1f} MB")
    print(f"wrote {args.dst}  ({args.dst.stat().st_size/1e6:.1f} MB, "
          f"was {args.src.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
