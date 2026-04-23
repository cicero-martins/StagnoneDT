"""
EDITO Datalab sync helper — upload v02 inputs, clean old outputs, list buckets.

Usage (from dfm_tools_env or any env with boto3 + python-dotenv):
    python scripts/edito_sync.py list
    python scripts/edito_sync.py clean-output
    python scripts/edito_sync.py clean-input
    python scripts/edito_sync.py upload [--model-dir PATH] [--prefix DFM_INPUT] [--dry-run]
    python scripts/edito_sync.py download-his [--output-prefix DFM_OUTPUT]

Credentials are read in order:
  1. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
     AWS_SESSION_TOKEN, AWS_S3_ENDPOINT
  2. .env file at f:/StagnoneDT/.env (same variable names)

Get your EDITO credentials at: https://datalab.dive.edito.eu/account/storage
They expire after a few hours/days — refresh the .env file when they do.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# botocore >= 1.36 adds checksum headers MinIO rejects — disable BEFORE boto3 import
os.environ.setdefault('AWS_REQUEST_CHECKSUM_CALCULATION', 'WHEN_REQUIRED')
os.environ.setdefault('AWS_RESPONSE_CHECKSUM_VALIDATION', 'WHEN_REQUIRED')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / 'model' / 'dflowfm_v03'  # default model version for upload/download
DOT_ENV = PROJECT_ROOT / '.env'

BUCKET = 'oidc-cmartinsjr'
DEFAULT_INPUT_PREFIX = 'DFM_INPUT'
DEFAULT_OUTPUT_PREFIX = 'DFM_OUTPUT'
DEFAULT_ENDPOINT = 'https://minio.dive.edito.eu'

EXCLUDE_DIRS = {'output', '__pycache__'}
EXCLUDE_SUFFIX = {'.cache'}
EXCLUDE_FILES = {'run_model.bat'}


def load_credentials() -> dict:
    """Resolve AWS_* from env vars, falling back to .env file."""
    if DOT_ENV.exists():
        for line in DOT_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    creds = {
        'aws_access_key_id': os.environ.get('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
        'aws_session_token': os.environ.get('AWS_SESSION_TOKEN'),
        'endpoint_url': os.environ.get('AWS_S3_ENDPOINT', DEFAULT_ENDPOINT),
    }
    if not creds['endpoint_url'].startswith('http'):
        creds['endpoint_url'] = 'https://' + creds['endpoint_url']

    missing = [k for k in ('aws_access_key_id', 'aws_secret_access_key') if not creds[k]]
    if missing:
        sys.exit(
            f'Missing credentials: {missing}\n'
            f'Set them as env vars or in {DOT_ENV} (see EDITO storage settings page).'
        )
    return creds


def get_client():
    import boto3
    from botocore.config import Config
    creds = load_credentials()
    endpoint = creds.pop('endpoint_url')
    # botocore >= 1.35 adds x-amz-sdk-checksum-algorithm headers by default on PUTs;
    # MinIO at EDITO rejects these and closes the connection → force "when_required".
    config = Config(
        retries={'max_attempts': 5, 'mode': 'adaptive'},
        connect_timeout=30,
        read_timeout=120,
        request_checksum_calculation='when_required',
        response_checksum_validation='when_required',
    )
    return boto3.client('s3', endpoint_url=endpoint, config=config, **creds)


def iter_local_files(root: Path):
    """Yield (local_path, key_suffix) pairs for files under root, filtered."""
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        # skip excluded dirs anywhere in the path
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.suffix in EXCLUDE_SUFFIX or p.name in EXCLUDE_FILES:
            continue
        yield p, rel.as_posix()


def human(n_bytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n_bytes < 1024:
            return f'{n_bytes:,.1f} {unit}'
        n_bytes /= 1024
    return f'{n_bytes:,.1f} PB'


def cmd_list(args):
    s3 = get_client()
    prefix = args.prefix.rstrip('/') + '/' if args.prefix else ''
    paginator = s3.get_paginator('list_objects_v2')
    total_n, total_b = 0, 0
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            total_n += 1
            total_b += obj['Size']
            print(f"{human(obj['Size']):>10}  {obj['Key']}")
    print(f"\n{total_n} object(s), {human(total_b)} total under s3://{BUCKET}/{prefix}")


def cmd_clean(prefix: str, confirm: bool):
    s3 = get_client()
    prefix = prefix.rstrip('/') + '/'
    paginator = s3.get_paginator('list_objects_v2')
    keys = [obj['Key'] for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix)
            for obj in page.get('Contents', [])]
    if not keys:
        print(f'Nothing to delete under {prefix}')
        return
    total_b = sum(
        obj['Size']
        for page in s3.get_paginator('list_objects_v2').paginate(Bucket=BUCKET, Prefix=prefix)
        for obj in page.get('Contents', [])
    )
    print(f'About to delete {len(keys)} object(s), {human(total_b)}, under s3://{BUCKET}/{prefix}')
    if confirm:
        ans = input('Proceed? [y/N] ').strip().lower()
        if ans != 'y':
            print('Aborted.')
            return
    # MinIO rejects batch delete_objects (MissingContentMD5) — delete one by one
    for i, k in enumerate(keys, 1):
        s3.delete_object(Bucket=BUCKET, Key=k)
        if i % 50 == 0 or i == len(keys):
            print(f'  deleted {i} / {len(keys)}')
    print('Done.')


def cmd_upload(args):
    src = Path(args.model_dir).resolve()
    if not src.is_dir():
        sys.exit(f'Source directory not found: {src}')
    prefix = args.prefix.rstrip('/') + '/'

    files = list(iter_local_files(src))
    total_b = sum(p.stat().st_size for p, _ in files)
    print(f'Source: {src}')
    print(f'Target: s3://{BUCKET}/{prefix}')
    print(f'Files:  {len(files)}   total {human(total_b)}')
    if args.dry_run:
        for p, k in files[:25]:
            print(f'  {human(p.stat().st_size):>10}  {k}')
        if len(files) > 25:
            print(f'  ... and {len(files) - 25} more')
        return

    s3 = get_client()
    uploaded_b = 0
    for i, (p, rel) in enumerate(files, 1):
        key = prefix + rel
        size = p.stat().st_size
        # Use put_object (single HTTP request) instead of upload_file (multipart + threads)
        # — MinIO at EDITO closes multipart connections on large files.
        with open(p, 'rb') as f:
            s3.put_object(Bucket=BUCKET, Key=key, Body=f.read())
        uploaded_b += size
        print(f'[{i:3d}/{len(files)}] {human(size):>10}  {key}   ({uploaded_b/total_b*100:.1f}%)')
    print(f'Uploaded {len(files)} file(s), {human(uploaded_b)}.')


def cmd_sync_code(args):
    """Upload notebooks + scripts + data/processed + memory-free project bits to CODE/.
    Skips: model/, data/raw/, .git/, __pycache__, .ipynb_checkpoints, .cache, .env.
    """
    src = PROJECT_ROOT
    prefix = args.prefix.rstrip('/') + '/'
    include_dirs = {'notebooks', 'scripts'}
    include_processed = src / 'data' / 'processed'

    files = []
    # top-level dirs we explicitly want
    for d in include_dirs:
        root = src / d
        if not root.exists():
            continue
        for p in root.rglob('*'):
            if not p.is_file():
                continue
            parts = p.relative_to(src).parts
            if '.ipynb_checkpoints' in parts or '__pycache__' in parts:
                continue
            if p.suffix in {'.pyc', '.cache'}:
                continue
            files.append((p, p.relative_to(src).as_posix()))
    # data/processed as lightweight helper artifacts (polygon csv, drifter csv, etc.)
    if include_processed.exists():
        for p in include_processed.rglob('*'):
            if p.is_file() and p.stat().st_size < 5 * 1024 * 1024:  # <5 MB
                files.append((p, p.relative_to(src).as_posix()))

    total_b = sum(p.stat().st_size for p, _ in files)
    print(f'Project root: {src}')
    print(f'Target:       s3://{BUCKET}/{prefix}')
    print(f'Files:        {len(files)}   total {human(total_b)}')
    if args.dry_run:
        for p, rel in files[:30]:
            print(f'  {human(p.stat().st_size):>10}  {rel}')
        if len(files) > 30:
            print(f'  ... and {len(files) - 30} more')
        return
    s3 = get_client()
    for i, (p, rel) in enumerate(files, 1):
        with open(p, 'rb') as f:
            s3.put_object(Bucket=BUCKET, Key=prefix + rel, Body=f.read())
        print(f'[{i:3d}/{len(files)}] {rel}')
    print(f'Uploaded {len(files)} file(s).')


def cmd_pull_code(args):
    """Mirror s3://<bucket>/CODE/ down into the local project root.
    Useful when notebooks/scripts were edited on another machine via the EDITO JupyterLab.
    Overwrites local files. Skips files outside notebooks/, scripts/, data/processed/.
    """
    s3 = get_client()
    prefix = args.prefix.rstrip('/') + '/'
    paginator = s3.get_paginator('list_objects_v2')
    objs = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            rel = obj['Key'][len(prefix):]
            if not rel:
                continue
            objs.append((obj['Key'], rel, obj['Size'], obj.get('LastModified')))

    if not objs:
        print(f'Nothing under s3://{BUCKET}/{prefix}')
        return

    print(f'Source: s3://{BUCKET}/{prefix}')
    print(f'Target: {PROJECT_ROOT}')
    print(f'Files:  {len(objs)}   total {human(sum(o[2] for o in objs))}')

    if args.dry_run:
        print('\nWould pull:')
        for key, rel, size, mtime in objs:
            local = PROJECT_ROOT / rel
            status = 'NEW' if not local.exists() else (
                'SAME-SIZE' if local.stat().st_size == size else 'CHANGED'
            )
            mt = mtime.strftime('%Y-%m-%d %H:%M') if mtime else '?'
            print(f'  [{status:9s}] {human(size):>10}  {mt}  {rel}')
        return

    for i, (key, rel, size, _) in enumerate(objs, 1):
        local = PROJECT_ROOT / rel
        local.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(BUCKET, key, str(local))
        print(f'[{i:3d}/{len(objs)}] {human(size):>10}  {rel}')
    print(f'Pulled {len(objs)} file(s).')


def cmd_download_his(args):
    """Fetch *_his.nc from DFM_OUTPUT/ to local model dir."""
    s3 = get_client()
    prefix = args.output_prefix.rstrip('/') + '/'
    model_dir = Path(args.model_dir).resolve() if args.model_dir else MODEL_DIR
    dst = model_dir / 'output'
    dst.mkdir(parents=True, exist_ok=True)
    paginator = s3.get_paginator('list_objects_v2')
    found = 0
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            k = obj['Key']
            if k.endswith('_his.nc'):
                local = dst / Path(k).name
                print(f'Downloading {k} -> {local}  ({human(obj["Size"])})')
                s3.download_file(BUCKET, k, str(local))
                found += 1
    if not found:
        print(f'No *_his.nc found under s3://{BUCKET}/{prefix}')


def main():
    ap = argparse.ArgumentParser(description='EDITO Datalab sync helper')
    sub = ap.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('list', help='List objects under a bucket prefix')
    s.add_argument('--prefix', default='', help='Prefix to list (default: whole bucket)')
    s.set_defaults(func=cmd_list)

    s = sub.add_parser('clean-input', help=f'Delete all under {DEFAULT_INPUT_PREFIX}/')
    s.add_argument('--yes', action='store_true', help='Skip confirmation')
    s.set_defaults(func=lambda a: cmd_clean(DEFAULT_INPUT_PREFIX, confirm=not a.yes))

    s = sub.add_parser('clean-output', help=f'Delete all under {DEFAULT_OUTPUT_PREFIX}/')
    s.add_argument('--yes', action='store_true', help='Skip confirmation')
    s.set_defaults(func=lambda a: cmd_clean(DEFAULT_OUTPUT_PREFIX, confirm=not a.yes))

    s = sub.add_parser('upload', help='Upload v02 inputs to DFM_INPUT/')
    s.add_argument('--model-dir', default=str(MODEL_DIR))
    s.add_argument('--prefix', default=DEFAULT_INPUT_PREFIX)
    s.add_argument('--dry-run', action='store_true')
    s.set_defaults(func=cmd_upload)

    s = sub.add_parser('sync-code', help='Upload notebooks + scripts + data/processed to CODE/')
    s.add_argument('--prefix', default='CODE')
    s.add_argument('--dry-run', action='store_true')
    s.set_defaults(func=cmd_sync_code)

    s = sub.add_parser('pull-code', help='Mirror CODE/ from S3 back into local project')
    s.add_argument('--prefix', default='CODE')
    s.add_argument('--dry-run', action='store_true')
    s.set_defaults(func=cmd_pull_code)

    s = sub.add_parser('download-his', help='Pull *_his.nc from DFM_OUTPUT/ to local')
    s.add_argument('--output-prefix', default=DEFAULT_OUTPUT_PREFIX)
    s.add_argument('--model-dir', default=None, help='Target local model dir (default: model/dflowfm_v03)')
    s.set_defaults(func=cmd_download_his)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
