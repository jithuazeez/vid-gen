"""Modal app — wires every leaf worker in `functions/` to a Modal Function
with the right GPU class and image. The bodies live in their own modules
(`apps/modal_app/functions/<name>.py`) so this file stays a thin manifest.

Architecture.md §5, §8.
"""
from __future__ import annotations

import os

import modal


# ---------------------------------------------------------------------------
# App + shared state
# ---------------------------------------------------------------------------

app = modal.App("vidplatform")
models_volume = modal.Volume.from_name("vidplatform-models", create_if_missing=True)


def _secret_or_none(name: str) -> modal.Secret | None:
    try:
        return modal.Secret.from_name(name)
    except Exception:
        return None


_secret_names = [
    "gemini-api-key", "sarvam-api-key", "aws-s3", "database-url", "redis-url",
    # Optional — only needed if you point LTX at a LoRA hosted in a
    # gated HuggingFace repo. The secret is loaded best-effort, so the
    # function still starts when it isn't configured.
    "huggingface-token",
]
secrets = [s for s in (_secret_or_none(n) for n in _secret_names) if s is not None]
secrets.append(modal.Secret.from_dict({"VIDPLATFORM_VERSION": "0.1.0"}))


# ---------------------------------------------------------------------------
# Base images
# ---------------------------------------------------------------------------

_cpu_base = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1", "git")
    .pip_install(
        "redis==5.2.0", "boto3==1.35.50",
        "psycopg[binary]==3.2.3", "sqlalchemy==2.0.36",
        "httpx==0.27.2", "structlog==24.4.0",
        "google-genai>=0.3", "Pillow>=10.0", "soundfile>=0.12",
    )
)

# add_local_python_source must be last — after all pip/apt build steps
cpu_image = _cpu_base.add_local_python_source("apps")

sdxl_image = _cpu_base.pip_install(
    "torch==2.4.0", "diffusers==0.30.3", "transformers==4.45.2",
    "accelerate==0.34.2", "safetensors==0.4.5",
).add_local_python_source("apps")
# LTX-Video 0.9.x via diffusers. We tried Lightricks's native LTX-2.3
# pipeline (`ltx-core` + `ltx-pipelines`) and gave up after three
# cascading upstream packaging bugs in a row (CUDA-13 torchaudio in their
# loose pins, an unshipped `multigpu/` subdirectory, a transformers
# SiglipVisionModel.vision_model rename). The 0.9.x line is older and
# weaker on motion, but it loads cleanly via stock diffusers and we can
# squeeze quality out of it via prompt design + an optional LoRA.
ltx_image = (
    _cpu_base.pip_install(
        "torch==2.4.0", "diffusers==0.32.2", "transformers==4.45.2",
        "imageio[ffmpeg]==2.36.0", "accelerate==0.34.2", "sentencepiece==0.2.0",
        "peft>=0.13",  # required by diffusers' LoRA loader
    )
    .env({
        "HF_HOME": "/models/hf",
        "HUGGINGFACE_HUB_CACHE": "/models/hf",
    })
    .add_local_python_source("apps")
)
musetalk_image = _cpu_base.pip_install(
    "torch==2.4.0", "opencv-python-headless==4.10.0.84",
    "ffmpeg-python==0.2.0", "librosa==0.10.2",
).add_local_python_source("apps")
# faster-whisper / ctranslate2 dlopen libcublas.so.12 and libcudnn.so.8 at
# first GPU call. debian_slim ships neither, so we pull them in as pip
# wheels and add their lib dirs to LD_LIBRARY_PATH. cuDNN must be the 8.x
# series — ctranslate2 4.4 links against cuDNN 8, not 9.
whisper_image = (
    _cpu_base.pip_install(
        "nvidia-cublas-cu12==12.4.5.8",
        "nvidia-cudnn-cu12==8.9.7.29",
        "faster-whisper==1.0.3",
        "ctranslate2==4.4.0",
    )
    .env({
        "LD_LIBRARY_PATH": (
            "/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:"
            "/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib"
        ),
    })
    .add_local_python_source("apps")
)
acestep_image = (
    _cpu_base.apt_install("git")
    .pip_install(
        "torch==2.4.0", "torchaudio==2.4.0",
        "transformers==4.45.2", "diffusers==0.30.3",
        "soundfile==0.12.1", "accelerate==0.34.2", "librosa==0.10.2",
        "huggingface_hub>=0.24",
    )
    .pip_install("git+https://github.com/ace-step/ACE-Step.git@main")
    # ACE-Step pulls flash-attn (and on main, FlashAttention-3) wheels
    # built against torch>=2.5. Their op signatures use PEP-604
    # `Tensor | None`, which torch 2.4's torch.library.infer_schema
    # can't parse — every container blows up at import time with
    # "Parameter q has unsupported type torch.Tensor".
    # Strip every flash-attn variant; ACE-Step falls back to torch's
    # native SDPA when none of them are importable. The env vars are a
    # belt-and-braces so transformers/diffusers don't try to opt in.
    .run_commands(
        "pip uninstall -y flash-attn flash-attn-3 flashattn-hopper "
        "flash_attn flash_attn_3 || true"
    )
    .env({
        "DISABLE_FLASH_ATTN": "1",
        "TRANSFORMERS_NO_FLASH_ATTN": "1",
        "FLASH_ATTENTION_DISABLE": "1",
    })
    .add_local_python_source("apps")
)
mediapipe_image = _cpu_base.pip_install(
    "mediapipe==0.10.18", "opencv-python-headless==4.10.0.84",
).add_local_python_source("apps")


# ---------------------------------------------------------------------------
# Day-1 smoke
# ---------------------------------------------------------------------------


@app.function(image=cpu_image, secrets=secrets, timeout=60)
def ping(project_id: str) -> dict:
    from apps.modal_app.functions._common import publish

    publish(project_id, "stage_change", {"stage": "ping", "from": "modal"})
    return {"ok": True, "project_id": project_id}


# ---------------------------------------------------------------------------
# Leaf workers — one Modal Function per model. Body is the matching module.
# ---------------------------------------------------------------------------


# Note: the Modal Function name (`sdxl_thumbnail`) and the image variable
# (`sdxl_image`) are intentionally different — the image gets passed as
# `image=sdxl_image`, the Function gets looked up by name from the Celery
# worker via `modal.Function.from_name`.

@app.function(image=sdxl_image, gpu="A10G", volumes={"/models": models_volume},
              secrets=secrets, timeout=120, name="sdxl_thumbnail")
def sdxl_thumbnail(project_id: str, scene_id: str, prompt: str, seed: int = 42) -> dict:
    from apps.modal_app.functions import thumbnails

    return thumbnails.run(project_id, scene_id, prompt, seed)


@app.function(image=sdxl_image, gpu="A10G", volumes={"/models": models_volume},
              secrets=secrets, timeout=180, name="sdxl_character_ref")
def sdxl_character_ref(project_id: str, character_id: str, name: str,
                       description: str, seed: int = 42) -> dict:
    from apps.modal_app.functions import character_refs

    return character_refs.run(project_id, character_id, name, description, seed)


@app.function(image=ltx_image, gpu="A100-40GB", volumes={"/models": models_volume},
              secrets=secrets, timeout=600)
def ltx_render(project_id: str, scene_id: str) -> dict:
    from apps.modal_app.functions import scene_video

    return scene_video.run(project_id, scene_id)


@app.function(image=cpu_image, secrets=secrets, timeout=120)
def generate_voice(project_id: str, scene_id: str, language: str) -> dict:
    from apps.modal_app.functions import voice

    return voice.run(project_id, scene_id, language)


@app.function(image=musetalk_image, gpu="A10G", volumes={"/models": models_volume},
              secrets=secrets, timeout=300)
def musetalk_sync(project_id: str, scene_id: str, language: str,
                   has_speaker: bool = True) -> dict | None:
    if not has_speaker:
        return None
    from apps.modal_app.functions import lipsync

    return lipsync.run(project_id, scene_id, language)


@app.function(image=whisper_image, gpu="T4", volumes={"/models": models_volume},
              secrets=secrets, timeout=240)
def whisper_align(project_id: str, scene_id: str, language: str) -> dict:
    from apps.modal_app.functions import subtitles

    return subtitles.run(project_id, scene_id, language)


@app.function(image=acestep_image, gpu="A10G", volumes={"/models": models_volume},
              secrets=secrets, timeout=240)
def acestep_music(project_id: str) -> dict | None:
    from apps.modal_app.functions import music

    return music.run(project_id)


@app.function(image=mediapipe_image, cpu=2, secrets=secrets, timeout=60)
def mediapipe_face(project_id: str, scene_id: str) -> dict:
    """Standalone MediaPipe pass — kept for cases where we want face data
    without doing a full subtitle pass (e.g. overlay placement). Subtitles
    runs its own face detect inline.
    """
    from apps.modal_app.functions import _common as cc
    from apps.modal_app.models import mediapipe_face as mpf

    sv = cc.fetch_asset_by_type(
        project_id=project_id, scene_id=scene_id,
        asset_type="scene_video", language=None,
    )
    if not sv:
        return {"position_hint": "bottom"}
    sv_path = cc.download_to_tmp(sv["storage_key"])
    res = mpf.detect(sv_path)
    cc.publish(project_id, "asset_progress",
               {"asset_type": "face_data", "scene_id": scene_id,
                "percent": 100, "position_hint": res.get("position_hint")})
    return res


@app.function(image=cpu_image, cpu=4, secrets=secrets, timeout=300)
def ffmpeg_composite(project_id: str, scene_id: str, language: str) -> dict:
    from apps.modal_app.functions import composite

    return composite.run(project_id, scene_id, language)


@app.function(image=cpu_image, cpu=4, secrets=secrets, timeout=600)
def final_export(project_id: str, language: str,
                 quality: str = "1080p", subtitles_mode: str = "burned") -> dict:
    from apps.modal_app.functions import export

    return export.run(project_id, language, quality, subtitles_mode)




@app.local_entrypoint()
def main(project_id: str = "00000000-0000-0000-0000-000000000000") -> None:
    print(ping.remote(project_id))
