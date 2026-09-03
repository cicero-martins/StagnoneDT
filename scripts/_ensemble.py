"""The ensemble definition, in one place.

Six analysis scripts each carried their own copy of the member list, which was
survivable at five members and stopped being so at eight: the 2x2x2 factorial
closed on 2026-08-08 once DensIn=false let the two no-wave mobile-bed cells run.
Adding a member meant editing six lists, and a grep that anchored on a name
prefix had already silently dropped two of them once.

The four mobile-bed members live in the *_dens directories. Their DensIn=true
predecessors are superseded: suspended sediment feeding the density field was
what aborted the no-wave pair, and it also produced a spurious 2.4 m
accumulation at 500 m depth. The fixed-bed members carry no sediment module, so
the parameter never applied to them and they are unchanged.

2026-08-31: the ROUGHNESS ARM CHANGED. It used to be the four *_vr members,
which carried the meadow as Baptist trachytopes. Two independent faults meant
those members were not resisting the flow -- the .arl reached 5.5% of the
meadow, and this build's trachytope canopy term never enters the momentum
equation -- so their contrasts measured almost nothing and the manuscript's
Section 4.3 drew the wrong conclusion from them. The arm is now FM's native
vegetation module, parameterised entirely from published measurement. The old
tags are kept below as LEGACY_VR because the diagnostics that established the
fault compare against them.
"""
import itertools

# key, drifter/regrid tag, model directory, waves, roughness, bed, short label
#
# The model directory does NOT follow from the tag for the vegetated members.
# They were built on the server under throwaway _veg_* names, and the fixed-bed
# member ran twice: _veg_hv040 is a one-day probe, _veg_hv040_3d is the three
# day run the ensemble actually uses. The authority is the `source` attribute
# written into each data/processed/*_surface_current.nc, not the name.
MEMBERS = [
    ('nowaves',       'v04AE_nowaves',            'dflowfm_v04AE_nowaves',
     False, 'uniform',     'fixed',  'no waves'),
    ('nowaves_veg',   'v04AE_veg_hv040',          '_veg_hv040_3d',
     False, 'vegetated',   'fixed',  'no waves\n+ canopy'),
    ('nodm',          'v04AE_nodm',               'dflowfm_v04AE_nodm',
     True,  'uniform',     'fixed',  'waves'),
    ('nodm_veg',      'v04AE_veg_waves',          '_veg_waves',
     True,  'vegetated',   'fixed',  'waves\n+ canopy'),
    ('nowaves_dm',    'v04AE_nowaves_dm',         'dflowfm_v04AE_nowaves_dm_dens',
     False, 'uniform',     'mobile', 'no waves\n+ morph.'),
    ('nowaves_vegdm', 'v04AE_veg_nowaves_dm',     '_veg_nowaves_dm',
     False, 'vegetated',   'mobile', 'no waves\n+ canopy\n+ morph.'),
    ('bl',            'v04AE',                    'dflowfm_v04AE_dens',
     True,  'uniform',     'mobile', 'waves\n+ morph.'),
    ('veg',           'v04AE_veg_waves_dm',       '_veg_waves_dm',
     True,  'vegetated',   'mobile', 'full'),
]

# Not an ensemble member. The vegetated members are three-day restart segments
# and the bare members are continuous nine-day runs, so a water level
# difference between the arms could in principle be the restart rather than the
# canopy. This is _veg_hv040_3d with the [veg] block and the three vegetation
# Parameter entries removed, same restart file, same window, so it differs from
# the continuous nowaves member only by being a segment.
#
# It answers no. At AltaVilaEst the continuous bare member gives an anomaly
# RMSE of 0.0510 m and the segment bare control gives 0.0508 m, correlation
# 0.82 in both, where the vegetated segment gives 0.0271 m and 0.94. The other
# two stations agree within 0.4 mm. The restart contributes nothing.
RESTART_CONTROL = ('v04AE_ctrl_noveg_seg', '_ctrl_noveg_seg')

# The superseded roughness arm: the meadow as Baptist trachytopes, before the
# .arl precision fix and before the inert canopy sink was established. Kept so
# compare_drifters_arlfix.py and compare_drifters_154.py can still address it.
LEGACY_VR = {
    'nowaves_veg':   'v04AE_nowaves_vr',
    'nodm_veg':      'v04AE_nodm_vr',
    'nowaves_vegdm': 'v04AE_nowaves_vrdm',
    'veg':           'v04AE_vr',
}

# The same four cells with the .arl written to nine decimals, so the meadow
# reaches the mesh, but still on Baptist 153. Corroborates the vegetated arm.
# The waves + mobile bed cell is absent: 153 with the meadow applied aborts
# there, and no run exists to compare.
ARLFIX = {
    'nowaves_veg':   'v04AE_nowaves_vr_arlfix',
    'nodm_veg':      'v04AE_nodm_vr_arlfix',
    'nowaves_vegdm': 'v04AE_nowaves_vrdm_arlfix',
}

# Nothing is excluded from the scored set. Deployment 4 is the one candidate
# and it stays in, deliberately.
#
# It is a sampling outlier by a factor of about 4.5 on three measures at once,
# with no intermediate case:
#
#     deployment 4    0.43 h    162 m observed path     3 scored steps
#     next lowest     1.94 h    723 m                  12 scored steps
#
# and Liu-Weisberg skill is cumulative separation over cumulative observed
# path, so at three steps a single fix dominates the statistic. The sampling
# case for dropping it is real.
#
# It stays in anyway because it is also the ONLY deployment where the bare-bed
# arm beats the vegetated arm (0.84/0.83/0.77 against 0.56/0.57/0.57), so
# removing it moves every headline number in the direction of the conclusion:
# the canopy contrasts widen from +0.195/+0.188/+0.256/+0.087 to
# +0.240/+0.230/+0.298/+0.095, and the wave contrast on a vegetated mobile bed
# goes from -0.014 to -0.002. An exclusion that only ever helps is the kind a
# reader is right to distrust, and the conclusion does not need it: every
# contrast keeps its sign and its significance with deployment 4 included.
#
# Use scored(df, exclude=(4,)) for the sensitivity numbers the manuscript
# reports beside the primary ones. sensitivity_deploy4.py prints both.
EXCLUDE_DEPLOYS = ()


def scored(df, exclude=EXCLUDE_DEPLOYS, verbose=True):
    """Drop the excluded deployments, saying so. Never drop them silently."""
    if not exclude:
        return df
    out = df[~df['deploy'].isin(exclude)]
    if verbose:
        n = len(df) - len(out)
        print(f'[scored] excluding deployment(s) {", ".join(map(str, exclude))}: '
              f'{n} drifter records dropped, {len(out)} kept')
    return out


KEYS = [m[0] for m in MEMBERS]
TAG = {m[0]: m[1] for m in MEMBERS}
MODELDIR = {m[0]: m[2] for m in MEMBERS}
LABEL = {m[0]: m[6] for m in MEMBERS}
FACTORS = {m[0]: dict(waves=m[3], roughness=m[4], bed=m[5]) for m in MEMBERS}

# Every single-factor contrast the closed factorial supports: four per factor,
# one for each combination of the two factors held fixed. Written as
# (label, treated, control) so the effect is treated minus control.
CONTRASTS = [
    ('Waves | bare, fixed bed',        'nodm',          'nowaves'),
    ('Waves | canopy, fixed bed',      'nodm_veg',      'nowaves_veg'),
    ('Waves | bare, mobile bed',       'bl',            'nowaves_dm'),
    ('Waves | canopy, mobile bed',     'veg',           'nowaves_vegdm'),

    ('Canopy | no waves, fixed bed',      'nowaves_veg',   'nowaves'),
    ('Canopy | waves, fixed bed',         'nodm_veg',      'nodm'),
    ('Canopy | no waves, mobile bed',     'nowaves_vegdm', 'nowaves_dm'),
    ('Canopy | waves, mobile bed',        'veg',           'bl'),

    ('Bed mobility | no waves, bare',  'nowaves_dm',    'nowaves'),
    ('Bed mobility | no waves, canopy',     'nowaves_vegdm', 'nowaves_veg'),
    ('Bed mobility | waves, bare',     'bl',            'nodm'),
    ('Bed mobility | waves, canopy',   'veg',           'nodm_veg'),
]


def cell(waves, roughness, bed):
    """The member key at a given corner of the factorial."""
    for k, f in FACTORS.items():
        if (f['waves'] == waves and f['roughness'] == roughness
                and f['bed'] == bed):
            return k
    raise KeyError((waves, roughness, bed))


def _assert_closed():
    """Every combination of the observed factor levels is a member, once.

    The factorial being closed is a premise of the whole analysis. Each of the
    twelve entries in CONTRASTS holds two factors fixed and varies the third,
    which measures a single-factor effect only if both corners exist and no
    corner is occupied twice. Nothing else in the module checks that, and an
    edit to MEMBERS that broke it would surface as a quietly missing bar in a
    figure rather than as an error.

    The levels come from MEMBERS rather than being written out here, so a
    deliberate change of design is read as such instead of tripping a
    hard-coded 2x2x2.
    """
    levels = [sorted({f[name] for f in FACTORS.values()}, key=str)
              for name in ('waves', 'roughness', 'bed')]
    shape = ' x '.join(str(len(lv)) for lv in levels)
    corners = list(itertools.product(*levels))
    if len(corners) != len(MEMBERS):
        raise AssertionError(
            f'{len(MEMBERS)} members against {len(corners)} corners of a '
            f'{shape} design: the factorial is not full')
    # Collisions are read off MEMBERS rather than off the sweep below, because
    # a collision always empties some other corner and cell() would reach that
    # one first, reporting an absence where the fault is a duplicate.
    at = {}
    for k, f in FACTORS.items():
        corner = (f['waves'], f['roughness'], f['bed'])
        if corner in at:
            raise AssertionError(
                f'members {at[corner]!r} and {k!r} both sit at {corner}')
        at[corner] = k

    for corner in corners:
        cell(*corner)              # KeyError names the corner that is absent


_assert_closed()
