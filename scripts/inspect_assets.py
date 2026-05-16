#!/usr/bin/env python3
"""Pull every asset for a project out of S3 and probe each file.

Usage:
    # List all assets for a project
    python scripts/inspect_assets.py <project_id>

    # Download them all into ./_inspect/<project_id>/ and ffprobe each one
    python scripts/inspect_assets.py <project_id> --download

    # Only specific asset types
    python scripts/inspect_assets.py <project_id> --download --types subtitle_srt,composite

Requires the same env as the API/worker:
    DATABASE_URL, S3_BUCKET, S3_ENDPOINT_URL (optional),
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_REGION
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import boto3
import psycopg
from psycopg.rows import dict_row


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    return (
        url.replace("postgresql+asyncpg://", "postgresql://")
           .replace("postgresql+psycopg://", "postgresql://")
    )


def list_assets(project_id: str, types: list[str] | None = None) -> list[dict]:
    where = ["a.project_id = %s"]
    params: list = [project_id]
    if types:
        where.append("a.asset_type = ANY(%s)")
        params.append(types)
    sql = f"""
        SELECT a.id, a.asset_type, a.language, a.storage_key, a.bytes,
               a.mime_type, a.content_hash, a.created_at,
               s.scene_index
        FROM assets a
        LEFT JOIN scenes s ON s.id = a.scene_id
        WHERE {" AND ".join(where)}
        ORDER BY a.asset_type, s.scene_index NULLS LAST, a.created_at
    """
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def s3_client():
    kwargs: dict = {"region_name": os.environ.get("S3_REGION", "us-east-1")}
    if ep := os.environ.get("S3_ENDPOINT_URL"):
        kwargs["endpoint_url"] = ep
    if k := os.environ.get("AWS_ACCESS_KEY_ID"):
        kwargs["aws_access_key_id"] = k
        kwargs["aws_secret_access_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    return boto3.client("s3", **kwargs)


def download(s3, bucket: str, key: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(dest))


def probe(path: Path) -> str:
    if not shutil.which("ffprobe"):
        return "(ffprobe not installed)"
    suffix = path.suffix.lower()
    if suffix in (".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a"):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format",
             "-of", "default=noprint_wrappers=1", str(path)],
            capture_output=True, text=True,
        )
        return r.stdout or r.stderr
    if suffix in (".srt", ".txt", ".vtt", ".json"):
        try:
            return path.read_text()[:2000]
        except Exception as e:
            return f"(read failed: {e})"
    return f"(no probe for {suffix})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project_id")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--types", help="comma-separated asset_types to include")
    ap.add_argument("--out", default="_inspect")
    args = ap.parse_args()

    types = [t.strip() for t in args.types.split(",")] if args.types else None
    rows = list_assets(args.project_id, types)
    print(f"# {len(rows)} assets for project {args.project_id}\n")

    bucket = os.environ.get("S3_BUCKET", "vidplatform")
    s3 = s3_client() if args.download else None
    out_root = Path(args.out) / args.project_id

    for r in rows:
        lang = r["language"] or "-"
        scene = r["scene_index"] if r["scene_index"] is not None else "-"
        line = (f"{r['asset_type']:18} scene={scene:>3} lang={lang:>3} "
                f"bytes={r['bytes'] or 0:>10}  id={r['id']}  key={r['storage_key']}")
        print(line)

        if args.download:
            ext = Path(r["storage_key"]).suffix or ".bin"
            dest = out_root / f"{r['asset_type']}_scene{scene}_{lang}_{str(r['id'])[:8]}{ext}"
            try:
                download(s3, bucket, r["storage_key"], dest)
                info = probe(dest).strip().splitlines()
                print(f"  -> {dest}")
                for ln in info[:12]:
                    print(f"     {ln}")
                if len(info) > 12:
                    print(f"     ... ({len(info)-12} more lines)")
            except Exception as e:
                print(f"  -> ERROR: {e}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
