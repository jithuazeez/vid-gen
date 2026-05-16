"""SDXL-Turbo loader — used for thumbnails and character reference images."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

_pipeline: Any = None


def load():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        import torch  # type: ignore
        from diffusers import AutoPipelineForText2Image  # type: ignore

        _pipeline = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float16,
            variant="fp16",
            cache_dir="/models/sdxl",
        ).to("cuda")
    except Exception:
        _pipeline = None
    return _pipeline


def generate(prompt: str, *, width: int = 1024, height: int = 576, seed: int = 42) -> Path:
    """Generate one image, return a local PNG/JPG path."""
    out = Path(tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name)
    pipe = load()
    if pipe is None:
        _write_placeholder_jpg(out, width, height, prompt[:80])
        return out
    try:
        import torch  # type: ignore

        gen = torch.Generator(device="cuda").manual_seed(int(seed))
        image = pipe(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=4,
            guidance_scale=0.0,
            generator=gen,
        ).images[0]
        image.save(str(out), "JPEG", quality=88)
    except Exception:
        _write_placeholder_jpg(out, width, height, prompt[:80])
    return out


def _write_placeholder_jpg(out: Path, width: int, height: int, label: str) -> None:
    """Pure-Python solid-colour placeholder so downstream pipeline still has a file."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (width, height), (24, 24, 28))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(8, 8), (width - 8, height - 8)], outline=(80, 80, 96), width=2)
        draw.text((20, 20), f"placeholder\n{label}", fill=(220, 220, 230))
        img.save(out, "JPEG", quality=80)
    except Exception:
        # Absolute last resort: write a 1-byte file so callers don't crash on stat().
        out.write_bytes(b"\xff")
