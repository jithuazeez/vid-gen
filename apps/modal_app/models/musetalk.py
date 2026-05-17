"""Lip-sync loader — wraps ByteDance LatentSync.

Despite the module name (kept for callsite stability — `lipsync.py` and
`render_project.py` import this), the backend is LatentSync, not
MuseTalk. We picked LatentSync because its dependency tree is clean
diffusers/transformers (no openmmlab/mmcv stack) and it ships
significantly better quality than Wav2Lip.

Container layout (configured in `apps/modal_app/app.py musetalk_image`):
  - repo clone at /opt/latentsync, on PYTHONPATH
  - configs/ and latentsync/utils/mask.png resolved as repo-relative
    paths, so the pipeline's CWD must be the clone (we chdir in load()).
  - checkpoints downloaded lazily to /models/latentsync/checkpoints/
    (the Modal volume), so cold-load is paid once per volume, not once
    per container.

Pipeline lives as a module-level singleton — first `load()` call in a
container pays the ~30-60s init, subsequent `sync()` calls reuse it.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

_pipeline: Any = None
_audio_encoder: Any = None
_config: Any = None
_dtype: Any = None


REPO_DIR = os.environ.get("LATENTSYNC_REPO_DIR", "/opt/latentsync")
CKPT_DIR = os.environ.get("LATENTSYNC_CKPT_DIR", "/models/latentsync/checkpoints")
UNET_CONFIG = os.environ.get("LATENTSYNC_UNET_CONFIG", "configs/unet/stage2.yaml")
INFERENCE_STEPS = int(os.environ.get("LATENTSYNC_INFERENCE_STEPS", "20"))
GUIDANCE_SCALE = float(os.environ.get("LATENTSYNC_GUIDANCE_SCALE", "1.5"))

# LatentSync's shipped mask.png is a hard-edged binary rectangle, which
# leaves a visible seam where the synthesized mouth region meets the
# original frame. Override with a Gaussian-feathered version so the
# paste-back blends smoothly. Regenerate via scripts/gen_feathered_mask.py
# if the upstream mask changes.
_FEATHERED_MASK = Path(__file__).resolve().parent.parent / "assets" / "lipsync_mask_feathered.png"


def _ensure_checkpoints() -> None:
    """Download LatentSync weights to the Modal volume on first call.

    Idempotent: skips files that already exist. The HF repo ships both
    1.5 and 1.6 weights under the same checkpoint name — same unet
    architecture, the only difference is training resolution selected
    via the unet config's ``resolution`` field.
    """
    from huggingface_hub import hf_hub_download

    unet_path = Path(CKPT_DIR) / "latentsync_unet.pt"
    whisper_path = Path(CKPT_DIR) / "whisper" / "tiny.pt"
    if unet_path.exists() and whisper_path.exists():
        return

    Path(CKPT_DIR).mkdir(parents=True, exist_ok=True)
    if not unet_path.exists():
        hf_hub_download(
            repo_id="ByteDance/LatentSync-1.6",
            filename="latentsync_unet.pt",
            local_dir=CKPT_DIR,
        )
    if not whisper_path.exists():
        hf_hub_download(
            repo_id="ByteDance/LatentSync-1.6",
            filename="whisper/tiny.pt",
            local_dir=CKPT_DIR,
        )


def load():
    global _pipeline, _audio_encoder, _config, _dtype
    if _pipeline is not None:
        return _pipeline

    _ensure_checkpoints()

    # LatentSync resolves configs and `latentsync/utils/mask.png` as
    # paths relative to CWD, so we have to chdir into the clone before
    # constructing the pipeline. We keep that working directory active
    # for sync() calls too.
    os.chdir(REPO_DIR)

    import torch  # type: ignore
    from omegaconf import OmegaConf  # type: ignore
    from diffusers import AutoencoderKL, DDIMScheduler  # type: ignore
    from latentsync.models.unet import UNet3DConditionModel  # type: ignore
    from latentsync.pipelines.lipsync_pipeline import LipsyncPipeline  # type: ignore
    from latentsync.whisper.audio2feature import Audio2Feature  # type: ignore

    config = OmegaConf.load(UNET_CONFIG)
    is_fp16 = torch.cuda.is_available() and torch.cuda.get_device_capability()[0] > 7
    dtype = torch.float16 if is_fp16 else torch.float32

    cross_dim = config.model.cross_attention_dim
    if cross_dim == 384:
        whisper_ckpt = str(Path(CKPT_DIR) / "whisper" / "tiny.pt")
    elif cross_dim == 768:
        whisper_ckpt = str(Path(CKPT_DIR) / "whisper" / "small.pt")
    else:
        raise NotImplementedError(
            f"LatentSync config cross_attention_dim={cross_dim} not supported "
            "(expected 384 or 768)"
        )

    audio_encoder = Audio2Feature(
        model_path=whisper_ckpt,
        device="cuda",
        num_frames=config.data.num_frames,
        audio_feat_length=config.data.audio_feat_length,
    )

    vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=dtype)
    vae.config.scaling_factor = 0.18215
    vae.config.shift_factor = 0

    unet_ckpt = str(Path(CKPT_DIR) / "latentsync_unet.pt")
    unet, _ = UNet3DConditionModel.from_pretrained(
        OmegaConf.to_container(config.model),
        unet_ckpt,
        device="cpu",
    )
    unet = unet.to(dtype=dtype)

    scheduler = DDIMScheduler.from_pretrained("configs")
    pipeline = LipsyncPipeline(
        vae=vae,
        audio_encoder=audio_encoder,
        unet=unet,
        scheduler=scheduler,
    ).to("cuda")

    _pipeline = pipeline
    _audio_encoder = audio_encoder
    _config = config
    _dtype = dtype
    return _pipeline


def sync(scene_video_path: str, voice_audio_path: str) -> Path:
    """Run LatentSync lip-sync, returning a path to the sync'd MP4."""
    import torch  # type: ignore

    pipeline = load()
    out = Path(tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name)
    temp_dir = tempfile.mkdtemp(prefix="latentsync_")

    pipeline(
        video_path=str(scene_video_path),
        audio_path=str(voice_audio_path),
        video_out_path=str(out),
        num_frames=_config.data.num_frames,
        num_inference_steps=INFERENCE_STEPS,
        guidance_scale=GUIDANCE_SCALE,
        weight_dtype=_dtype,
        width=_config.data.resolution,
        height=_config.data.resolution,
        mask_image_path=str(_FEATHERED_MASK),
        temp_dir=temp_dir,
    )
    torch.cuda.empty_cache()
    return out
