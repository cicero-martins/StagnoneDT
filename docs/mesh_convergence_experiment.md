# Convergence of the v04 mesh and layer count

Section 3.1 of Paper 1 states the mesh resolution and the ten sigma layers as
the constraints they answer, with the explicit note that no convergence test
stands behind either. That note is honest and it is also an opening. The
experiment below closes it, and the cost is dominated by mesh construction
rather than by compute.

## What the resolution has to be adequate for

Water level is the wrong target. The manuscript's own result is that water
level separates the eight ensemble members by 36 mm at the one gauge inside
the vegetated basin and by 2 and 9 mm near the inlets, so a mesh that
reproduces water level says nothing about the quantity the paper reports.

Four quantities carry the question, each tied to the choice it tests.

| Quantity | Tests | Where it is already reported |
|---|---|---|
| Volume flux and tidal prism at each inlet | horizontal resolution at the throats | not reported |
| Liu–Weisberg skill over the 35 drifters | the paper's target quantity | Section 4.2 |
| Surface-to-bed speed ratio, lagoon interior | the layer count | Section 4.4 |
| Anomaly RMSE at BocaNord, AltaVilaEst, BocaSud | control, expected flat | Section 4.1 |

The first is the one the northern inlet concern turns on, and it is the one
the manuscript does not currently carry.

## Which cells set the time step

The cost of refinement depends on whether the refined region controls the
time step, and at the present resolution the lagoon does not.

| Region | Spacing | Depth | Courant limit at CFL 0.7 |
|---|---|---|---|
| Lagoon interior | 61 m | 1 m | 13.6 s |
| Lagoon southern basin | 61 m | 3 m | 7.9 s |
| Shoreline refinement bands | 55 m | 3 m | 7.1 s |
| Open offshore background | 880 m | 730 m | 7.3 s |

The realised mean step in the reference run is 6.90 s, which matches the
shoreline bands and the open background and sits well below the lagoon's
13.6 s. Refining the lagoon from 61 m to 30 m brings its limit to 6.8 s, level
with what already binds, so that step buys cells without buying time steps.
Refining to 15 m brings it to 3.4 s and the global step halves.

The prediction is checkable for the price of one model-definition key.
`Wrimap_numlimdt = 1` writes, per cell, the number of times that cell limited
the step. It is off in every run to date.

## Members

Seven runs, one of which is the shared reference. The design is three ladders
rather than a factorial, since convergence is approach to a limit and not
interaction.

| Member | Mesh | Layers | Purpose |
|---|---|---|---|
| L0 | base, 61 m in the lagoon | 10 | reference, and `numlimdt` on |
| L1 | lagoon split 2×, 30 m | 10 | mesh ladder |
| L2 | lagoon split 4×, 15 m | 10 | mesh ladder |
| P1 | inlet throats split 2×, 30 m | 10 | isolates the inlets |
| P2 | inlet throats split 4×, 15 m | 10 | isolates the inlets |
| K5 | base | 5 | layer ladder |
| K20 | base | 20 | layer ladder |

L0, L1 and L2 form a ratio-2 ladder, which is what a Grid Convergence Index
needs to return an observed order of convergence and an error band on the base
mesh. P1 and P2 answer whether whatever L1 and L2 show comes from the inlets
alone or from the basin as a whole, which is the difference between a local
fix and a rebuilt mesh. K5, K10 and K20 form the vertical ladder, with L0
serving as K10.

Refining a mesh also resolves more bathymetric detail, so numerical
convergence and bathymetric convergence move together unless they are
separated. One pair should carry the same smoothed bed interpolated onto both
meshes, which isolates the numerics.

## Simulated window

All twelve drifter deployments fall between 8 July 2025 07:14 and 9 July
12:07, and the longest runs 7.2 h, so every drifter is out of the water by
about 19:00 on 9 July. A segment from 7 July 00:00 to 10 July 00:00 covers the
whole Lagrangian target with 31 h of spin-up ahead of the first release, at a
third of the cost of the nine-day window.

The refined meshes cannot restart from the base mesh's restart files, which
are bound to a mesh and a partition count, so every member cold-starts from
the prescribed hypersaline initial field and discards its first day. All
members share that treatment, which is what makes the comparison internally
consistent.

## Cost

Scaling is anchored on a measured run rather than a flop count. The no-waves
bathy26 twin covered nine simulated days over 25,212 faces and 10 layers on
four MPI ranks of the local 4-core machine in 2 h 40 min, across 112,673
computational steps. Wall time is taken proportional to faces × layers ×
steps, with the step count following from whichever Courant limit binds.
`scripts/size_convergence_experiment.py` reproduces the table.

| Member | Faces | Step | 3 d | 9 d |
|---|---|---|---|---|
| L0 | 25,212 | 6.9 s | 0h53 | 2h40 |
| L1 | 40,119 | 6.8 s | 1h26 | 4h18 |
| L2 | 99,747 | 3.4 s | 7h07 | 21h22 |
| P1 | 27,411 | 6.8 s | 0h59 | 2h56 |
| P2 | 36,207 | 3.4 s | 2h35 | 7h45 |
| K5 | 25,212 | 6.9 s | 0h27 | 1h20 |
| K20 | 25,212 | 6.9 s | 1h47 | 5h20 |

### The two machines

The two are distinct machines and are easily conflated, since both are
dual-socket Xeons.

| | simit, Linux | workstation, Windows |
|---|---|---|
| CPU | 2× Xeon Gold 5220R, 24 cores a socket | 2× Xeon Gold 6430, 32 cores a socket |
| Cores | 48 physical, 96 threads | 64 physical |
| Memory | 188 GB DDR4, 6 of 12 slots filled | 128 GB DDR5 |
| Stack | RHEL 8.7, Intel MPI 2021.10 | Windows 11, MS-MPI |

The 96 that appears in some notes for simit is its thread count, which is
what `nproc` reports, and not a core count. Planning here uses the 48 physical
cores, since hyperthreading carries no benefit for SWAN by PRACE WP177 and the
flow solver is bound by MPI communication and memory bandwidth by WP284. The
figures date from 2026-05-15 and are worth reconfirming with `lscpu` once the
server is reachable.

A controlled comparison on that date ran the same nine-day coupled v04AE at
eight ranks on both machines. Wall time was 3.05 h on the server against
7.68 h on the workstation, but the flow solver's own time was 8723 s against
7676 s. The server is marginally slower at the flow solver, and the entire
2.5× advantage sits in the SWAN and DIMR coupling.

These runs carry no waves. The server therefore buys no speed per member, and
what it buys is the ability to run every member at once.

| | Ranks a member | At a time | 3 d serial | 3 d batched | 9 d serial | 9 d batched |
|---|---|---|---|---|---|---|
| Local, 4 cores | 4 | 1 | 15h13 | 15h13 | 45h39 | 45h39 |
| simit, 48 cores | 6 | 7 | 14h55 | **6h59** | 44h44 | **20h56** |

Peak memory for all seven at once is about 47 GB against the server's 188 GB,
extrapolated from the 0.28 GB per rank measured on the running member. Memory
does not constrain the design.

The consequence is that on the server the nine-day window costs about one day
of wall time for the whole set, which removes the reason to accept the
three-day segment and its truncated spin-up. The local machine cannot do this
in any reasonable time and is currently occupied by the bathy26 control.

## The cost that is not compute

Building L1, L2, P1 and P2 is the real expense. The attempt of 2026-05-27 to
2026-05-29 to build a v05 mesh spent two to three days and ended blocked on
FM 2026.01 rejecting the network as not orthogonal, a check that meshkernel's
own orthogonality metric does not reproduce. The v04 mesh in production
carries 9.55% of cells with the circumcentre outside the cell and still runs,
so the metric is not the criterion the solver applies.

That attempt merged a hand-built lagoon mesh into a new offshore grid.
Polygon-bounded refinement of an existing mesh is a different operation, since
splitting a quadrilateral or a triangle into four preserves its shape and only
the transition band between refined and unrefined cells introduces new
geometry. The risk is lower and it is not zero, and the transition band is
where it lives. One to two days is the realistic budget, with the possibility
that L2 refuses to initialise.

`scripts/build_mesh_v05.py` and the orthogonalisation helpers from that
session are on disk and are the starting point.

## Sequence

Ordered so that each stage returns something usable on its own and the risky
work comes last.

| Stage | Members | Mesh work | Compute, 9 d on the server | What it settles |
|---|---|---|---|---|
| 1 | K5, K20 | none | 6h40 | the layer count, outright |
| 2 | L0 with `numlimdt` | none | 2h40 | which cells bind the step |
| 3 | P1, P2 | localised | 10h41 | whether the inlets are the problem |
| 4 | L1, L2 | full lagoon | 25h40 | the Grid Convergence Index |

Stages 1 and 2 need no new mesh and together cost under half a day of server
time. They convert half of the open item into a reported result at no
construction risk. Stage 3 answers the northern inlet question directly. Stage
4 is the formal convergence study and is the only stage carrying the mesh
construction risk in full.

## Interaction with the 2026 bathymetry

The new raster shrinks the cross-section of the northern inlet throat by 26%
against the v04 bed, and the v04 mesh is 7 to 20 cm too deep over the first
90 m from shore. A mesh certified for convergence against the v04 bed would be
certified against a throat a quarter too large, at exactly the location the
resolution question concerns.

The two decisions are therefore not separable in the direction that matters.
Convergence certifies a mesh for a bed, and the ladder and the production
ensemble should share one bed. If the ensemble is to be rerun on the 2026
bathymetry, the ladder should be built on it first and the rerun should use
whatever resolution the ladder certifies, which costs one ordering decision
and no extra compute.

The raster is not usable outside the lagoon, being 1.1 m deeper than v04 on
the outer slope of the northern inlet and 1.3 m deeper on average beyond the
2006 footprint, so the bed in question is the patched one the bathy26 twin
already uses, v04 with the raster blended over the lagoon and a 500 m linear
ramp outwards.

## Placement in the manuscript

Figures stand at eight against a limit of eight and tables at three against
three, so a convergence figure displaces something. The journal accepts
supplementary material, which is where a convergence table and a GCI figure
belong, with Section 3.1 carrying the result in two sentences and the
reference to the supplement.
