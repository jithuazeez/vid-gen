"""LTX-Video 0.9.x I2V loader via diffusers, with optional LoRA.

We're on the 0.9.x line because LTX-2.3 isn't loadable through diffusers
yet and Lightricks's native pipeline package has too many unshipped/
mispinned dependencies to integrate reliably. To make 0.9.x produce
better motion than its default behavior:

  • Prompt building lives in `scene_video._build_ltx_prompt` and is
    motion-first (camera moves and subject action lead the prompt).
  • An optional LoRA can be attached via env vars without code changes:
        LTX_LORA_REPO       HuggingFace repo id (e.g. user/ltx-cinematic)
        LTX_LORA_FILE       filename within the repo (.safetensors)
        LTX_LORA_SCALE      float multiplier, default 1.0
    Useful community LoRAs trained on cinematic/anime/stop-motion data
    can lift the output substantially over the bare distilled model.
  • Inference steps and guidance scale are env-overridable too.

Set ``LTX_ALLOW_PLACEHOLDER=1`` to opt back into the offline ffmpeg
stub for local dev without a GPU.
"""
from __future__ import annotations

import inspect
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_pipeline: Any = None
MODEL_ID = os.environ.get("LTX_MODEL_ID", "Lightricks/LTX-Video")


def load():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    import torch  # type: ignore
    from diffusers import LTXImageToVideoPipeline  # type: ignore

    _pipeline = LTXImageToVideoPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        cache_dir="/models/ltx",
    ).to("cuda")

    _maybe_attach_lora(_pipeline)
    return _pipeline


def _maybe_attach_lora(pipe) -> None:
    """Attach a community LoRA when configured. Best-effort — a load
    failure logs a warning and falls through to the bare base model."""
    repo = os.environ.get("LTX_LORA_REPO")
    file = os.environ.get("LTX_LORA_FILE")
    if not repo or not file:
        return
    scale = float(os.environ.get("LTX_LORA_SCALE", "1.0"))
    adapter_name = os.environ.get("LTX_LORA_ADAPTER", "extra")
    token = os.environ.get("HF_TOKEN")
    try:
        kwargs: dict[str, Any] = {
            "weight_name": file,
            "adapter_name": adapter_name,
        }
        if token:
            kwargs["token"] = token
        pipe.load_lora_weights(repo, **kwargs)
        if hasattr(pipe, "set_adapters"):
            pipe.set_adapters([adapter_name], adapter_weights=[scale])
        print(f"[ltx] attached LoRA {repo}/{file} @ scale={scale}")
    except Exception as e:  # pragma: no cover — runtime-best-effort
        print(f"[ltx] warning: LoRA load failed for {repo}/{file}: {e}")


def _snap32(n: int) -> int:
    """LTX requires height/width divisible by 32."""
    return max(32, int(round(n / 32)) * 32)


def run_i2v(
    *,
    prompt: str,
    conditioning_image_path: str | None,
    duration_s: float,
    width: int = 768,
    height: int = 448,
    fps: int = 24,
    seed: int = 42,
    negative_prompt: str | None = None,
) -> Path:
    width, height = _snap32(width), _snap32(height)
    out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)

    if os.environ.get("LTX_ALLOW_PLACEHOLDER") == "1" and conditioning_image_path is None:
        _write_placeholder_video(out, duration_s, width, height, fps)
        return out

    if conditioning_image_path is None:
        raise RuntimeError(
            "LTX i2v requires a conditioning image (thumbnail or character_ref) "
            "but none was provided. Check that Phase A thumbnails/character_refs ran "
            "and that fetch_asset_by_type returns a row for this scene."
        )
    if not prompt or not prompt.strip():
        raise RuntimeError("LTX i2v requires a non-empty prompt.")

    import torch  # type: ignore
    from PIL import Image, ImageOps  # type: ignore

    pipe = load()
    src = Image.open(conditioning_image_path).convert("RGB")
    cond = ImageOps.fit(src, (width, height), method=Image.LANCZOS, centering=(0.5, 0.5))
    gen = torch.Generator(device="cuda").manual_seed(int(seed))
    num_frames = max(8, int(round(duration_s * fps)))
    steps = int(os.environ.get("LTX_NUM_INFERENCE_STEPS", "40"))
    guidance = float(os.environ.get("LTX_GUIDANCE_SCALE", "3.0"))

    call_kwargs: dict[str, Any] = dict(
        image=cond,
        prompt=prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        num_inference_steps=steps,
        guidance_scale=guidance,
        generator=gen,
    )
    if negative_prompt:
        call_kwargs["negative_prompt"] = negative_prompt
    call_kwargs = _filter_kwargs(pipe.__call__, call_kwargs)
    result = pipe(**call_kwargs)

    # LTXPipelineOutput(frames=[[PIL,...]]) → unwrap the first batch.
    raw = getattr(result, "frames", None)
    if raw is None:
        raw = result[0]
    frames = raw[0] if (raw and isinstance(raw[0], list)) else raw
    if not frames:
        raise RuntimeError("LTX pipeline returned zero frames.")
    _write_frames_mp4(frames, out, fps)
    return out


def _filter_kwargs(fn, kwargs: dict) -> dict:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


def _write_frames_mp4(frames, out: Path, fps: int) -> None:
    import imageio.v2 as iio

    seq = []
    for f in frames:
        if hasattr(f, "convert"):
            seq.append(iio.imread(str(_save_pil(f))))
        else:
            seq.append(f)
    iio.mimsave(
        str(out), seq, fps=fps, codec="libx264", quality=8,
        macro_block_size=1, output_params=["-pix_fmt", "yuv420p"],
    )


def _save_pil(img):
    p = Path(tempfile.NamedTemporaryFile(suffix=".png", delete=False).name)
    img.save(p)
    return p


def _write_placeholder_video(out: Path, duration_s: float, w: int, h: int, fps: int) -> None:
    """Solid-colour MP4 stub (used in offline/no-GPU dev)."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=#181820:s={w}x{h}:r={fps}:d={max(1.0, duration_s):.2f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out),
        ],
        check=True,
    )
