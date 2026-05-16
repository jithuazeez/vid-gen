"""Model loaders — kept separate from `functions/` so the same loader can
be reused across multiple Modal functions and (e.g. for SDXL) across
both the thumbnails and character-refs entry points.

Loaders are lazy: they spin up the model on first call inside the Modal
container, then keep it warm for subsequent invocations on the same
container (Modal recycles containers between calls when scale-to-zero
hasn't kicked in yet).
"""
