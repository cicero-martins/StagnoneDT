"""Attribution of the eight-member ensemble rerun from the stratified start.

Runs attribution_stats.py unchanged except for the member tags, which point to
the members started from the depth profiles of the CMEMS nudging field
(build_ic3d_profiles.py) instead of the uniform 24 C and 37.5 column, and for
the output file, data/processed/attribution_contrasts_ic3d.csv. The bare
members are the ensemble members with initialFields.ini replaced, and each
vegetated member is its three-day segment restarted on 7 July from the bare
member of the same cell (scripts/_ic3d_ensemble_simit.sh).
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
IC3D_TAGS = {
    'nowaves': 'v04AE_nowaves_ic3d',
    'nowaves_veg': 'v04AE_veg_hv040_ic3d',
    'nodm': 'v04AE_nodm_ic3d',
    'nodm_veg': 'v04AE_veg_waves_ic3d',
    'nowaves_dm': 'v04AE_nowaves_dm_ic3d',
    'nowaves_vegdm': 'v04AE_veg_nowaves_dm_ic3d',
    'bl': 'v04AE_ic3d',
    'veg': 'v04AE_veg_waves_dm_ic3d',
}

src = (HERE / 'attribution_stats.py').read_text(encoding='utf-8')
assert src.count('MEMBERS = TAG') == 1 and src.count("PROC / 'attribution_contrasts.csv'") == 1
src = src.replace('MEMBERS = TAG', f'MEMBERS = {IC3D_TAGS!r}')
src = src.replace('attribution_contrasts.csv', 'attribution_contrasts_ic3d.csv')
exec(compile(src, str(HERE / 'attribution_stats.py'), 'exec'), {'__name__': '__main__', '__file__': str(HERE / 'attribution_stats.py')})
