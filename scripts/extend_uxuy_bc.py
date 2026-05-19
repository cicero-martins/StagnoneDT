"""Extend uxuyadvectionvelocitybnd_CMEMS_*.bc by appending a duplicate of the
last data row per [Forcing] block with new timestamps, so FM doesn't hit EOF
during a continuation run beyond the original .bc's last time.

Input:  model/dflowfm_v04AE/uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc
Output: model/dflowfm_v04AE_d10d12/uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc

The .bc has 49 [Forcing] blocks. Each block: header + vertPositions + quantity
declarations + data rows (time + 100 values). The script appends 2 extra rows
per block at t = last_time + (Jul 13, 17280 min after Jul 10 00:00).
"""
from __future__ import annotations
from pathlib import Path

SRC = Path('model/dflowfm_v04AE/uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc')
DST = Path('model/dflowfm_v04AE_d10d12/uxuyadvectionvelocitybnd_CMEMS_Stagnone_dxy01_15m.bc')

# Time unit: minutes since 2025-01-01 00:00:00
# Last existing time in source: 274320 min (Jul 10 12:00)
# Append two extra entries:
#   - Jul 12 12:00 = 192.5 days = 277200 min  (mid-window safety)
#   - Jul 13 12:00 = 193.5 days = 278640 min  (beyond simulation end Jul 12 00:00)
EXTRA_TIMES = [277200.0, 278640.0]


def is_data_row(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s.startswith('[') or s.startswith('#'):
        return False
    # heuristic: data rows start with a number
    first = s.split()[0]
    try:
        float(first)
        return True
    except ValueError:
        return False


def extend(src: Path, dst: Path):
    lines = src.read_text().splitlines(keepends=False)
    out: list[str] = []
    block_data_lines: list[str] = []  # accumulating data rows of current block

    def flush_block_extension():
        """Before writing the next block header (or EOF), append extension rows
        derived from the last data row of the just-finished block."""
        if not block_data_lines:
            return
        last = block_data_lines[-1]
        # split: first token = time, rest = values
        parts = last.split()
        values_part = ' '.join(parts[1:])  # everything after the time
        # detect leading whitespace of the data row for cosmetic consistency
        prefix = last[:len(last) - len(last.lstrip())]
        for t in EXTRA_TIMES:
            new_row = f'{prefix}{t:<8g}  {values_part}'
            out.append(new_row)

    in_data = False
    for line in lines:
        if line.startswith('[Forcing]'):
            # end of previous block (if any): flush extension
            flush_block_extension()
            block_data_lines = []
            in_data = False
            out.append(line)
        elif is_data_row(line):
            block_data_lines.append(line)
            in_data = True
            out.append(line)
        else:
            # header / structural line
            in_data = False
            out.append(line)

    # Flush extension for the LAST block (no trailing [Forcing] to trigger it)
    flush_block_extension()

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text('\n'.join(out) + '\n')
    print(f'Extended {src.name} -> {dst}')
    print(f'  source lines : {len(lines)}')
    print(f'  output lines : {len(out)}')
    print(f'  appended {len(EXTRA_TIMES)} rows per block x 49 blocks = {len(EXTRA_TIMES)*49} extra data rows')


if __name__ == '__main__':
    extend(SRC, DST)
