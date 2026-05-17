"""LTX-2 image-to-video via diffusers, with optional dual-image conditioning.

We use `LTX2ConditionPipeline` so a scene can be anchored by **two** reference
images at the same time: the per-scene SDXL thumbnail at the opening latent
frame (composition / framing / set / lighting), and the project-wide
character_ref at a mid-latent index with reduced strength (identity hint
without forcing it as a literal frame). Either can be omitted; at least one
must be supplied.

LTX-2 emits an audio tensor alongside the video. The caller decides whether
to persist it via the ``want_audio`` flag — for scenes that have a speaker
we ignore the audio (narration + lip-sync covers it); for the rest we keep
it as the scene's audio track.

Environment overrides (all optional):
  LTX_MODEL_ID                  HuggingFace repo (default Lightricks/LTX-2)
  LTX_LORA_REPO, LTX_LORA_FILE, LTX_LORA_SCALE, LTX_LORA_ADAPTER
                                Attach a community LoRA on top of the base.
  LTX2_NUM_INFERENCE_STEPS      Default 30.
  LTX2_GUIDANCE_SCALE           Default 3.0.
  LTX2_STG_SCALE                Default 1.0 (spatio-temporal guidance).
                                Set to 0 to disable STG entirely.
  LTX2_STG_BLOCKS               Comma-separated transformer block indices for
                                STG. Default "29" (LTX-2.0); use "28" for
                                LTX-2.3. Ignored when LTX2_STG_SCALE=0.
  LTX2_CHARREF_STRENGTH         Mid-latent character_ref strength, default 0.5.
  LTX_ALLOW_PLACEHOLDER=1       Offline ffmpeg stub when no refs are present.
"""
from __future__ import annotations

import inspect
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_pipeline: Any = None
MODEL_ID = os.environ.get("LTX_MODEL_ID", "Lightricks/LTX-2")


def load():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    import torch  # type: ignore
    from diffusers import LTX2ConditionPipeline  # type: ignore

    _pipeline = LTX2ConditionPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        cache_dir="/models/ltx2",
    )
    # 19B model on A100-40GB: model-level CPU offload moves whole sub-modules
    # (text encoder → transformer → VAE) on/off GPU rather than swapping
    # individual layers. ~5–10× faster than sequential offload while still
    # fitting 40GB because only one sub-module is GPU-resident at a time.
    # Do *not* `.to("cuda")` — that defeats the offloader.
    _pipeline.enable_model_cpu_offload()

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
    thumbnail_path: str | None,
    character_ref_path: str | None,
    duration_s: float,
    width: int = 768,
    height: int = 448,
    fps: int = 24,
    seed: int = 42,
    negative_prompt: str | None = None,
    want_audio: bool = False,
) -> tuple[Path, Path | None]:
    """Run LTX-2 image-to-video with up to two reference images.

    Returns ``(video_mp4_path, audio_wav_path_or_None)``. ``audio`` is only
    written when ``want_audio`` is true and the pipeline returns a non-empty
    audio tensor.
    """
    width, height = _snap32(width), _snap32(height)
    video_out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)

    if (thumbnail_path is None and character_ref_path is None
            and os.environ.get("LTX_ALLOW_PLACEHOLDER") == "1"):
        _write_placeholder_video(video_out, duration_s, width, height, fps)
        return video_out, None

    if thumbnail_path is None and character_ref_path is None:
        raise RuntimeError(
            "LTX-2 requires at least one conditioning image (thumbnail or "
            "character_ref) but none was provided. Check that Phase A "
            "thumbnails/character_refs ran and that fetch_asset_by_type "
            "returns a row for this scene."
        )
    if not prompt or not prompt.strip():
        raise RuntimeError("LTX-2 requires a non-empty prompt.")

    import numpy as np  # type: ignore
    import torch  # type: ignore
    from PIL import Image, ImageOps  # type: ignore
    from diffusers.pipelines.ltx2.pipeline_ltx2_condition import (  # type: ignore
        LTX2VideoCondition,
    )

    pipe = load()
    gen = torch.Generator(device="cuda").manual_seed(int(seed))
    num_frames = max(8, int(round(duration_s * fps)))
    steps = int(os.environ.get("LTX2_NUM_INFERENCE_STEPS", "30"))
    guidance = float(os.environ.get("LTX2_GUIDANCE_SCALE", "3.0"))
    stg = float(os.environ.get("LTX2_STG_SCALE", "1.0"))
    stg_blocks = [
        int(x) for x in os.environ.get("LTX2_STG_BLOCKS", "29").split(",") if x.strip()
    ]
    charref_strength = float(os.environ.get("LTX2_CHARREF_STRENGTH", "0.5"))

    def _load(p: str):
        return ImageOps.fit(
            Image.open(p).convert("RGB"),
            (width, height),
            method=Image.LANCZOS,
            centering=(0.5, 0.5),
        )

    conditions: list[LTX2VideoCondition] = []
    if thumbnail_path is not None:
        conditions.append(
            LTX2VideoCondition(frames=_load(thumbnail_path), index=0, strength=1.0)
        )
    if character_ref_path is not None:
        ratio = getattr(pipe, "vae_temporal_compression_ratio", None) \
            or getattr(getattr(pipe, "vae", None), "temporal_compression_ratio", None) \
            or 8
        latent_frames = max(1, num_frames // int(ratio))
        mid_idx = max(0, latent_frames // 2)
        conditions.append(
            LTX2VideoCondition(
                frames=_load(character_ref_path),
                index=mid_idx,
                strength=charref_strength,
            )
        )

    call_kwargs: dict[str, Any] = dict(
        conditions=conditions,
        prompt=prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        frame_rate=float(fps),
        num_inference_steps=steps,
        guidance_scale=guidance,
        generator=gen,
        output_type="np",
        return_dict=False,
    )
    if stg > 0 and stg_blocks:
        call_kwargs["stg_scale"] = stg
        call_kwargs["spatio_temporal_guidance_blocks"] = stg_blocks
    if negative_prompt:
        call_kwargs["negative_prompt"] = negative_prompt
    call_kwargs = _filter_kwargs(pipe.__call__, call_kwargs)
    result = pipe(**call_kwargs)

    # LTX-2 returns (video, audio) when return_dict=False.
    video, audio = (result + (None,))[:2] if isinstance(result, tuple) else (result, None)
    # Video shape varies: ndarray (T,H,W,C) or batched (B,T,H,W,C) or list.
    if isinstance(video, np.ndarray):
        frames_arr = video[0] if video.ndim == 5 else video
    elif isinstance(video, list):
        frames_arr = video[0] if (video and isinstance(video[0], list)) else video
    else:
        frames_arr = video
    if frames_arr is None or (hasattr(frames_arr, "__len__") and len(frames_arr) == 0):
        raise RuntimeError("LTX-2 pipeline returned zero frames.")
    _write_frames_mp4(frames_arr, video_out, fps)

    audio_out: Path | None = None
    if want_audio and audio is not None:
        try:
            sample_rate = int(pipe.vocoder.config.output_sampling_rate)
        except Exception:
            sample_rate = 44100
        audio_out = Path(tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name)
        _write_wav(audio, audio_out, sample_rate)

    return video_out, audio_out


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
    import numpy as np  # type: ignore

    seq = []
    if isinstance(frames, np.ndarray):
        # (T,H,W,C); cast to uint8 if it came back as float in [0,1].
        arr = frames
        if arr.dtype != np.uint8:
            arr = np.clip(arr * 255.0 if arr.max() <= 1.0 + 1e-3 else arr, 0, 255).astype(np.uint8)
        seq = [arr[i] for i in range(arr.shape[0])]
    else:
        for f in frames:
            if hasattr(f, "convert"):
                seq.append(iio.imread(str(_save_pil(f))))
            elif isinstance(f, np.ndarray):
                seq.append(f if f.dtype == np.uint8 else np.clip(f, 0, 255).astype(np.uint8))
            else:
                seq.append(f)
    iio.mimsave(
        str(out), seq, fps=fps, codec="libx264", quality=8,
        macro_block_size=1, output_params=["-pix_fmt", "yuv420p"],
    )


def _write_wav(audio, out: Path, sample_rate: int) -> None:
    """Write LTX-2's audio tensor to a 16-bit PCM WAV.

    LTX-2 returns float audio in roughly [-1, 1]. We normalise to peak ~0.95
    to avoid clipping in ffmpeg downstream and to keep levels predictable
    against the (separate) TTS path.
    """
    import numpy as np  # type: ignore
    import soundfile as sf  # type: ignore

    arr = audio
    if hasattr(arr, "detach"):
        arr = arr.detach().float().cpu().numpy()
    arr = np.asarray(arr, dtype=np.float32)
    # Expected shapes: (samples,), (channels, samples), or batched (B, ...).
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim == 2 and arr.shape[0] in (1, 2) and arr.shape[1] > arr.shape[0]:
        arr = arr.T  # (samples, channels)
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 0:
        arr = arr * (0.95 / peak)
    sf.write(str(out), arr, sample_rate, subtype="PCM_16")


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
