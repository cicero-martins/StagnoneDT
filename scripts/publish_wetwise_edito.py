"""Publish the WetWise portal to EDITO S3 as a public static site.

The portal is plain HTML/JS plus binary field files, so it needs object storage
and nothing else -- no Streamlit, no server.  This uploads index.html and the
data/ payload under a prefix and makes that prefix anonymously readable, which
is what turns it into a shareable link.

Credentials come from .env (gitignored).  EDITO issues OIDC session tokens that
expire in about a day; the token only gates *uploading*, so an already published
portal keeps working after it lapses.  Refresh the three AWS_* values from the
EDITO Datalab UI when the upload starts failing with "Access Key Id ... does not
exist".

    python scripts/publish_wetwise_edito.py
    python scripts/publish_wetwise_edito.py --html-only   # after a front-end tweak
"""
from pathlib import Path
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PORTAL = ROOT / 'outputs' / 'wetwise_tab' / 'demo_hydrodynamics'
BUCKET = 'oidc-cmartinsjr'
PREFIX = 'wetwise-portal'
ALIAS = 'edpub'          # transient, defined through the environment only


def load_env():
    env = {}
    path = ROOT / '.env'
    if not path.exists():
        sys.exit('.env not found')
    for line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
                           'AWS_SESSION_TOKEN', 'AWS_S3_ENDPOINT')
               if not env.get(k)]
    if missing:
        sys.exit('missing in .env: ' + ', '.join(missing))
    return env


def token_expiry(tok):
    if tok.count('.') != 2:
        return None
    try:
        p = tok.split('.')[1]
        p += '=' * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p)).get('exp')
    except Exception:
        return None


def mc_env(env):
    host = env['AWS_S3_ENDPOINT'].split('://', 1)[-1]
    out = dict(os.environ)
    out['MC_HOST_' + ALIAS] = 'https://{}:{}:{}@{}'.format(
        env['AWS_ACCESS_KEY_ID'], env['AWS_SECRET_ACCESS_KEY'],
        env['AWS_SESSION_TOKEN'], host)
    return out


def run(args, environ, **kw):
    mc = shutil.which('mc') or shutil.which('mc.exe')
    if not mc:
        sys.exit('mc not on PATH')
    return subprocess.run([mc] + args, env=environ, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html-only', action='store_true',
                    help='push index.html only, skipping the data payload')
    args = ap.parse_args()

    if not (PORTAL / 'index.html').exists():
        sys.exit(f'no portal at {PORTAL} -- run the build first')

    env = load_env()
    exp = token_expiry(env['AWS_SESSION_TOKEN'])
    if exp:
        left = (exp - time.time()) / 3600
        if left <= 0:
            sys.exit('EDITO session token expired -- refresh AWS_* in .env')
        print(f'token valid for {left:.1f} h')

    environ = mc_env(env)
    dest = f'{ALIAS}/{BUCKET}/{PREFIX}'

    print('uploading index.html ...')
    run(['cp', str(PORTAL / 'index.html'), f'{dest}/index.html'],
        environ, check=True)

    if not args.html_only:
        size = sum(p.stat().st_size for p in (PORTAL / 'data').rglob('*')
                   if p.is_file()) / 1e6
        print(f'uploading data/ ({size:.0f} MB) ...')
        # mirror, not `cp --recursive`: cp appends the source directory name to
        # the destination, which silently produces data/data/... and a portal
        # that 404s on every field file.
        run(['mirror', '--overwrite', '--quiet',
             str(PORTAL / 'data'), f'{dest}/data'], environ, check=True)

    print('making the prefix anonymously readable ...')
    run(['anonymous', 'set', 'download', dest], environ, check=True)

    url = '{}/{}/{}/index.html'.format(
        env['AWS_S3_ENDPOINT'].rstrip('/'), BUCKET, PREFIX)
    print('\npublic URL:\n  ' + url)


if __name__ == '__main__':
    main()
