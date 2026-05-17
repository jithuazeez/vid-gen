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
    .apt_install("ffmpeg", "libsndfile1")
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
# Lip-sync via ByteDance LatentSync. The repo is a script project (not a
# pip package), so we git-clone it into the image at a pinned SHA and add
# the checkout to PYTHONPATH so ``from latentsync.pipelines... import
# LipsyncPipeline`` resolves. Picked over MuseTalk because LatentSync's
# dependency tree is clean diffusers/transformers (no openmmlab/mmcv).
# Picked over Wav2Lip because LatentSync ships visibly higher quality
# (audio-conditioned latent diffusion vs. pixel-space CNN).
#
# Default config is ``stage2.yaml`` (256x256, ~8 GB VRAM, the LatentSync
# 1.5 inference path). To upgrade to 1.6 quality (512x512, ~18 GB VRAM),
# set ``LATENTSYNC_UNET_CONFIG=configs/unet/stage2_512.yaml`` in the
# image env — same checkpoint, different resolution.
LATENTSYNC_REPO_SHA = "a229c3948406bc2cf6eaf4873e662e70c6a04746"  # 2025-06-20
musetalk_image = (
    _cpu_base
    .apt_install("git", "libgl1")
    .pip_install(
        # Match LatentSync's pinned requirements.txt exactly to avoid
        # subtle numerics drift from version mismatches.
        "torch==2.5.1", "torchvision==0.20.1",
        "diffusers==0.32.2", "transformers==4.48.0",
        "decord==0.6.0", "accelerate==0.26.1", "einops==0.7.0",
        "omegaconf==2.3.0", "opencv-python==4.9.0.80",
        "mediapipe==0.10.11", "python_speech_features==0.6",
        "librosa==0.10.1", "scenedetect==0.6.1",
        "ffmpeg-python==0.2.0", "imageio==2.31.1",
        "imageio-ffmpeg==0.5.1", "lpips==0.1.4",
        "face-alignment==1.4.1", "huggingface-hub==0.30.2",
        "numpy==1.26.4", "kornia==0.8.0", "insightface==0.7.3",
        "onnxruntime-gpu==1.21.0", "DeepCache==0.1.1",
        extra_options="--extra-index-url https://download.pytorch.org/whl/cu121",
    )
    .run_commands(
        f"git clone https://github.com/bytedance/LatentSync /opt/latentsync && "
        f"cd /opt/latentsync && git checkout {LATENTSYNC_REPO_SHA}",
    )
    .env({
        "HF_HOME": "/models/hf",
        "HUGGINGFACE_HUB_CACHE": "/models/hf",
        # PYTHONPATH lets `import latentsync` resolve to the clone. CWD
        # matters because the inference pipeline reads relative paths
        # (configs/, latentsync/utils/mask.png).
        "PYTHONPATH": "/opt/latentsync",
        "LATENTSYNC_REPO_DIR": "/opt/latentsync",
        "LATENTSYNC_CKPT_DIR": "/models/latentsync/checkpoints",
        "LATENTSYNC_UNET_CONFIG": "configs/unet/stage2.yaml",
        "LATENTSYNC_INFERENCE_STEPS": "20",
        "LATENTSYNC_GUIDANCE_SCALE": "1.5",
    })
    .add_local_python_source("apps")
)
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


# SDXL-Turbo is shared by `thumbnail` and `character_ref`. We host both as
# methods on a single `@app.cls` so the pipeline loads exactly once per
# container via `@modal.enter`, then services every scene's thumbnails and
# the project's character_refs from the same warm GPU. With
# `scaledown_window=120` the container survives the full render's image
# phase, so the 10–15s cold-load tax is paid once per project instead of
# once per call.
#
# Worker callers look these up via `modal.Cls.from_name("vidplatform", "Sdxl")`
# and invoke `.thumbnail.spawn(...)` / `.character_ref.spawn(...)`.

@app.cls(image=sdxl_image, gpu="A10G", volumes={"/models": models_volume},
         secrets=secrets, timeout=180, scaledown_window=120)
class Sdxl:
    @modal.enter()
    def _load(self) -> None:
        # Warms the module-level singleton in models/sdxl.py so subsequent
        # method calls in this container skip cold load.
        from apps.modal_app.models import sdxl as sdxl_model

        sdxl_model.load()

    @modal.method()
    def thumbnail(self, project_id: str, scene_id: str, prompt: str, seed: int = 42) -> dict:
        from apps.modal_app.functions import thumbnails

        return thumbnails.run(project_id, scene_id, prompt, seed)

    @modal.method()
    def character_ref(self, project_id: str, character_id: str, name: str,
                      description: str, seed: int = 42,
                      frontal: bool = False) -> dict:
        from apps.modal_app.functions import character_refs

        return character_refs.run(project_id, character_id, name, description,
                                  seed=seed, frontal=frontal)


@app.function(image=ltx_image, gpu="A100-40GB", volumes={"/models": models_volume},
              secrets=secrets, timeout=600)
def ltx_render(project_id: str, scene_id: str) -> dict:
    from apps.modal_app.functions import scene_video

    return scene_video.run(project_id, scene_id)


@app.function(image=cpu_image, secrets=secrets, timeout=120)
def generate_voice(project_id: str, scene_id: str, language: str) -> dict:
    from apps.modal_app.functions import voice

    return voice.run(project_id, scene_id, language)


# LatentSync lip-sync. Timeout sized for first-call cold path: ~3-5 min
# weight download (latentsync_unet.pt ~5 GB + whisper/tiny.pt) on first
# invocation against a fresh volume, then ~30-60 s pipeline init, then
# ~10 s/scene inference. scaledown_window keeps the container warm so
# subsequent scenes in the same project reuse the loaded pipeline.
@app.function(image=musetalk_image, gpu="A10G", volumes={"/models": models_volume},
              secrets=secrets, timeout=900, scaledown_window=300)
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


@app.function(image=mediapipe_image, cpu=2, secrets=secrets, timeout=60)
def mediapipe_face(project_id: str, scene_id: str) -> dict:
    """Run MediaPipe face detection on a scene_video and persist the result
    as a ``face_data`` asset. Consumers (overlay auto-placement, subtitle
    fallback) query the assets table by ``(scene_id, asset_type='face_data')``
    and read ``metadata.position_hint`` / ``metadata.frames``.

    Subtitles still runs its own face-detect inline for the moment, but
    that path falls back to ``"bottom"`` when nothing's cached; once this
    asset exists it can be reused without re-decoding the video. The
    standalone path also fires for non-speaker scenes (those don't run
    whisper_align), so overlays get face data for every scene.
    """
    import json
    import tempfile
    from pathlib import Path

    from apps.modal_app import storage as st
    from apps.modal_app.functions import _common as cc
    from apps.modal_app.models import mediapipe_face as mpf

    sv = cc.fetch_asset_by_type(
        project_id=project_id, scene_id=scene_id,
        asset_type="scene_video", language=None,
    )
    if not sv:
        return {"position_hint": "bottom", "asset_id": None}

    h = st.content_hash({
        "scene_video_storage_key": sv.get("storage_key"),
        "kind": "face_data",
        "v": os.environ.get("CACHE_VERSION", "v3"),
    })
    cached = cc.cached_or(h)
    if cached:
        cc.publish(project_id, "asset_progress",
                   {"asset_type": "face_data", "scene_id": scene_id,
                    "percent": 100, "cache_hit": True})
        return {**cached, "position_hint": (cached.get("metadata") or {}).get("position_hint", "bottom")}

    sv_path = cc.download_to_tmp(sv["storage_key"])
    res = mpf.detect(sv_path)

    # Persist the JSON blob so consumers can fetch it without re-running
    # the detector. The asset's metadata also carries position_hint so
    # cheap lookups (overlay placement) don't need to download the file.
    out = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
    out.write_text(json.dumps(res), encoding="utf-8")
    key = st.asset_key(project_id=project_id, asset_type="face_data",
                       short_hash=h[:8], extension="json",
                       scene_index=scene_id)
    bytes_ = st.upload_file(out, key, "application/json")
    record = st.register_asset(
        project_id=project_id, scene_id=scene_id,
        asset_type="face_data", language=None,
        storage_key=key, content_hash_value=h,
        bytes_=bytes_, mime_type="application/json",
        metadata={"position_hint": res.get("position_hint", "bottom"),
                  "sample_count": len(res.get("frames") or [])},
    )
    cc.publish(project_id, "asset_progress",
               {"asset_type": "face_data", "scene_id": scene_id,
                "percent": 100, "position_hint": res.get("position_hint"),
                "asset_id": record.get("asset_id")})
    return {**record, "position_hint": res.get("position_hint", "bottom")}


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
