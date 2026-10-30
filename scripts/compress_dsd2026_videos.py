# -*- coding: utf-8 -*-
"""Re-encode the embedded videos of the Delft3D User Days deck.

The seven MP4 parts account for 138 of the 164 MB the deck occupies. Six of
them are screen captures written by the recorder at 4.5 to 6.3 Mb/s, which is
far above what a mostly static user interface needs, and the four captured from
Chrome carry an AAC track at digital silence, measured at -91 dB.

The pass keeps every resolution and every duration, so the shapes and any trim
set in PowerPoint stay valid. It lowers the rate to a constant quality factor
and drops the silent tracks. The replacement happens at the package level,
since the relationships address the parts by name and the content type does not
change.

Usage:
    python scripts/compress_dsd2026_videos.py
    python scripts/compress_dsd2026_videos.py --crf 26 --in <deck> --out <deck>
"""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DECK_IN = ROOT / "docs" / "dsd2026" / "dsd2026_cmj_vf_lineage.pptx"
DECK_OUT = ROOT / "docs" / "dsd2026" / "dsd2026_cmj_vf_lineage_light.pptx"


def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(ff, src, dst, crf):
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)


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
    targets = [n for n in src_zip.namelist()
               if n.startswith("ppt/media/") and n.lower().endswith(".mp4")]

    replacement, before, after = {}, 0, 0
    for name in sorted(targets):
        raw = work / (Path(name).stem + "_in.mp4")
        out = work / (Path(name).stem + "_out.mp4")
        raw.write_bytes(src_zip.read(name))
        encode(ff, raw, out, args.crf)
        data = out.read_bytes()
        before += raw.stat().st_size
        after += len(data)
        replacement[name] = data
        print(f"  {Path(name).name:<12} {raw.stat().st_size/1e6:7.1f} -> "
              f"{len(data)/1e6:6.1f} MB", flush=True)

    with zipfile.ZipFile(args.dst, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for item in src_zip.infolist():
            data = replacement.get(item.filename) or src_zip.read(item.filename)
            out_zip.writestr(item, data)
    src_zip.close()
    shutil.rmtree(work, ignore_errors=True)

    print(f"video {before/1e6:.1f} -> {after/1e6:.1f} MB")
    print(f"wrote {args.dst}  ({args.dst.stat().st_size/1e6:.1f} MB, "
          f"was {args.src.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
