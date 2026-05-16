"""Leaf worker functions, one per model.

Each module exports a Modal-decorated callable that:
  1. Computes the canonical content_hash of its inputs.
  2. Looks up the assets table for a cache hit; returns immediately on hit.
  3. Otherwise: runs the model, uploads the artifact to S3, registers the
     asset row, publishes an SSE progress event, returns the asset record.

No orchestration logic lives here — the Celery worker fans these out.
"""
