#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import List, Dict

HASH_ALGO = 'sha256'
MANIFEST_NAME = 'manifest.json'
FIXED_MTIME = 0
FILE_MODE = 0o644


def sha256_bytes(data: bytes) -> str:
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def read_input_files(input_dir: Path) -> List[Dict[str, object]]:
    if not input_dir.is_dir():
        raise SystemExit(f'ERROR: input-dir is not a directory: {input_dir}')
    entries = []
    seen_paths = set()
    for p in sorted(input_dir.rglob('*')):
        if p.is_dir():
            continue
        rel = p.relative_to(input_dir).as_posix()
        # Canonical v1 layout places replay report with other artifacts.
        if rel == 'replay_audit_report.json':
            rel = 'artifacts/replay_audit_report.json'
        if rel in seen_paths:
            raise SystemExit(f'ERROR: duplicate canonical path in input-dir: {rel}')
        seen_paths.add(rel)
        data = p.read_bytes()
        entries.append({
            'path': rel,
            'bytes': data,
            'size': len(data),
            'sha256': sha256_bytes(data),
        })
    if not entries:
        raise SystemExit(f'ERROR: no files found under input-dir: {input_dir}')
    return sorted(entries, key=lambda e: e['path'])


def manifest_payload(files: List[Dict[str, object]]) -> bytes:
    # Files are already sorted by canonical relative path.
    manifest = {
        'bundle_version': 'attestation_bundle_v1',
        'hash_algo': HASH_ALGO,
        'files': [
            {
                'path': f['path'],
                'sha256': f['sha256'],
                'size': f['size'],
            }
            for f in files
        ],
    }
    return (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')


def add_bytes(tf: tarfile.TarFile, arcname: str, data: bytes) -> None:
    ti = tarfile.TarInfo(name=arcname)
    ti.size = len(data)
    ti.mtime = FIXED_MTIME
    ti.uid = 0
    ti.gid = 0
    ti.uname = ''
    ti.gname = ''
    ti.mode = FILE_MODE
    tf.addfile(ti, io.BytesIO(data))


def cmd_pack(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    out_path = Path(args.out)
    files = read_input_files(input_dir)
    manifest_bytes = manifest_payload(files)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Uncompressed tar for deterministic bytes without compression metadata variability.
    with tarfile.open(out_path, mode='w:', format=tarfile.USTAR_FORMAT) as tf:
        add_bytes(tf, MANIFEST_NAME, manifest_bytes)
        for f in files:
            add_bytes(tf, f"payload/{f['path']}", f['bytes'])

    bundle_bytes = out_path.read_bytes()
    print(f'WROTE={out_path}')
    print(f'BUNDLE_SHA256={sha256_bytes(bundle_bytes)}')
    print(f'MANIFEST_SHA256={sha256_bytes(manifest_bytes)}')
    print('MANIFEST_FILES=' + ','.join(f['path'] for f in files))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='Attestation bundle v1 deterministic pack (pack only)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p_pack = sub.add_parser('pack')
    p_pack.add_argument('--input-dir', required=True)
    p_pack.add_argument('--out', required=True)
    p_pack.set_defaults(func=cmd_pack)
    args = ap.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
