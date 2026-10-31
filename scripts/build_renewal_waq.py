"""D-Water Quality input for the renewal of the lagoon, on the hydrodynamics of FM.

Four conservative tracers are transported offline on the volumes, flows and
vertical diffusivity written by FM (waqInterval) and merged by waqmerge.

    cTR1  water of the southern basin, 1 there at the start, 0 elsewhere
    cTR2  water of the central basin
    cTR3  water of the northern basin
    cTR4  sea water, 1 outside the lagoon at the start and at the open boundary

The basins are those of renewal_common. The four sum to 1 everywhere, which
checks the conservation of the transport, and the first three sum to the
lagoon_tracer of FM, which checks the coupling against the online solution.
Each basin tracer gives the remaining fraction of the basin and, inside the
other basins, the exchange between them, which the single online tracer cannot
separate.

Horizontal transport uses scheme 15, implicit upwind, which carries no Courant
limit on the cells of 15 m, and the vertical dispersion is the eddy
diffusivity of FM through the process VertDisp.

Usage:
    python build_renewal_waq.py <hyd file> <model dir> <run dir>
        [--start 2025/07/01-00:00:00] [--stop 2025/07/10-00:00:00]
        [--step 0000500] [--output-step 0010000]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from renewal_common import basin_id, lagoon_faces

SUBSTANCES = ["cTR1", "cTR2", "cTR3", "cTR4"]


def read_hyd(path: Path) -> dict:
    keys = {}
    for line in path.read_text().splitlines():
        p = line.split(None, 1)
        if len(p) == 2:
            keys[p[0]] = p[1].strip().strip("'")
    return keys


def initial_fields(geom: Path, model_dir: Path, nlay: int) -> np.ndarray:
    """(substance, segment) initial concentrations, segments layer by layer from the top."""
    with xr.open_dataset(geom) as g:
        x, y = g.mesh2d_face_x.values, g.mesh2d_face_y.values
    b = basin_id(y, lagoon_faces(model_dir, x, y))
    face = np.stack([(b == 1), (b == 2), (b == 3), (b == 0)]).astype(float)
    print(f"faces per layer {x.size}: southern {int(face[0].sum())}, central {int(face[1].sum())}, "
          f"northern {int(face[2].sum())}, sea {int(face[3].sum())}")
    return np.tile(face, (1, nlay))


def block(values: np.ndarray, per_line: int = 20) -> str:
    return "\n".join(" ".join(f"{v:.0f}" for v in values[i:i + per_line])
                     for i in range(0, values.size, per_line))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("hyd", type=Path)
    ap.add_argument("model_dir", type=Path, help="holds lagoon_tracer_init.xyz")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--start", default="2025/07/01-00:00:00")
    ap.add_argument("--stop", default="2025/07/10-00:00:00")
    ap.add_argument("--step", default="0000500", help="ddhhmmss")
    ap.add_argument("--output-step", default="0010000", help="ddhhmmss")
    args = ap.parse_args(argv)

    hyd = read_hyd(args.hyd)
    d = args.hyd.parent.resolve()
    f = {k: f"'{d / hyd[k]}'" for k in ("volumes-file", "areas-file", "flows-file", "pointers-file",
                                         "lengths-file", "vert-diffusion-file", "attributes-file",
                                         "horizontal-surfaces-file", "waqgeom-file")}
    nper = int(hyd["number-water-quality-segments-per-layer"])
    nlay = int(hyd["number-water-quality-layers"])
    nseg = nper * nlay
    nq1 = int(hyd["number-horizontal-exchanges"])
    nq3 = int(hyd["number-vertical-exchanges"])
    poi = np.fromfile(d / hyd["pointers-file"], dtype=np.int32).reshape(-1, 4)
    nbnd = int(-poi[:, :2].min()) if poi[:, :2].min() < 0 else 0
    print(f"{nseg} segments in {nlay} layers, {nq1} + {nq3} exchanges, {nbnd} boundary segments")
    init = initial_fields(d / hyd["waqgeom-file"], args.model_dir, nlay)

    run = args.run_dir
    run.mkdir(parents=True, exist_ok=True)
    with open(run / "initials.inc", "w") as fh:
        for name, v in zip(SUBSTANCES, init):
            fh.write(f"INITIALS\n'{name}'\nALL\nDATA\n{block(v)}\n")
    bnd_lines = "\n".join(f"'{i}' 'bnd{i}' 'sea'" for i in range(1, nbnd + 1))
    bnd_data = ("ITEM\n'sea'\nCONCENTRATIONS\n" + " ".join(f"'{s}'" for s in SUBSTANCES)
                + "\nDATA\n0.0 0.0 0.0 1.0\n") if nbnd else ""
    subs = "\n".join(f"{i:4d}  '{s}'" for i, s in enumerate(SUBSTANCES, 1))
    out = f"{args.start} {args.stop} {args.output_step}"

    inp = f"""1000 132 ';'    ; width of input and output, comment
;
; Type of DELWAQ input file:
; DELWAQ_VERSION_4.91
; Option for printing the report: verbose
; PRINT_OUTPUT_OPTION_4
;
; first block: identification
'Renewal of the Stagnone lagoon'
'Conservative tracers of the three basins and of the sea'
'{hyd['hydrodynamic-file']}'
'T0: {hyd['reference-time'][:4]}.{hyd['reference-time'][4:6]}.{hyd['reference-time'][6:8]} 00:00:00  (scu=       1s)'
;
 {len(SUBSTANCES)}  0    ; number of active and inactive substances
{subs}
;
#1 ; delimiter for the first block
;
; second block of model input (timers)
 86400 'ddhhmmss' 'ddhhmmss' ; system clock in sec, aux in days
 15.70    ; integration option
 {args.start}  ; start time
 {args.stop}  ; stop time
 0        ; constant timestep
 {args.step}  ; time step
;
 1     ; monitoring points/areas used
 0     ; number of monitoring points/areas
 2     ; monitoring transects not used
;
 {out}  ; monitoring
 {out}  ; map, dump
 {out}  ; history
;
#2 ; delimiter for the second block
;
; third block of model input (grid layout)
UGRID {f['waqgeom-file']}
 {nseg}  ; number of segments
MULTIGRID
  ZMODEL NOLAY {nlay}
END_MULTIGRID
 2    ; grid layout not used
;
INCLUDE {f['attributes-file']}  ; attributes file
;
-2  ; first volume option
{f['volumes-file']}  ; volumes file
;
#3 ; delimiter for the third block
;
; fourth block of model input (transport)
 {nq1}  ; exchanges in direction 1
 0  ; exchanges in direction 2
 {nq3}  ; exchanges in direction 3
;
 0 ; number of dispersion arrays
 0 ; number of velocity arrays
;
 1  ; first form is used for input
 0  ; exchange pointer option
{f['pointers-file']}  ; pointers file
;
 1  ; first dispersion option nr
 1.0 1.0 1.0   ; scale factors in three directions
 1.0 0.0 0.0   ; dispersion in x, y and z directions
;
 -2  ; first area option
{f['areas-file']}  ; area file
;
 -2  ; first flow option
{f['flows-file']}  ; flow file
;
 1  ; length vary
 0  ; length option
{f['lengths-file']}  ; length file
;
#4 ; delimiter for the fourth block
;
; fifth block of model input (boundary conditions)
{bnd_lines}
;
 0 ; no Thatcher-Harleman time lags
;
{bnd_data}
#5 ; delimiter for the fifth block
;
; sixth block of model input (discharges, withdrawals, waste loads)
 0 ; number of waste loads
#6 ; delimiter for the sixth block
;
; seventh block of model input (process parameters)
CONSTANTS 'ONLY_ACTIVE' DATA 1.0
CONSTANTS 'ACTIVE_VertDisp' DATA 1.0
PARAMETERS 'Surf' ALL BINARY_FILE {f['horizontal-surfaces-file']}
SEG_FUNCTIONS 'VertDisper' LINEAR ALL BINARY_FILE {f['vert-diffusion-file']}
#7 ; delimiter for the seventh block
;
; eighth block of model input (initial conditions)
 MASS/M2 ; unit for inactive substances
INCLUDE 'initials.inc'
#8 ; delimiter for the eighth block
;
; ninth block of model input (output)
 1 ; conditions follow
 2 ; all substances and extra output, monitor
 0 ; number of extra variables
 2 ; all substances and extra output, grid
 0
 2 ; history
 0
 2 ; map
 0
 1 ; binary history file on
 1 ; binary map file on
 1 ; nefis history file on
 1 ; nefis map file on
#9 ; delimiter for the ninth block
;
; tenth block of model input (statistics)
#10 ; delimiter for the tenth block
"""
    (run / "renewal.inp").write_text(inp)
    print(f"wrote {run / 'renewal.inp'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
