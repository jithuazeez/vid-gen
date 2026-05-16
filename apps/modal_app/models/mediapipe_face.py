"""MediaPipe face detection sampled at N=5 frames per scene.

Architecture.md §17 (Subtitle position auto-decision): if the face bbox
vertical centre is in the bottom 33% of the frame for ≥3 of 5 frames,
choose `top` for subtitle placement; else `bottom`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

Position = Literal["top", "bottom"]


def detect(scene_video_path: str, samples: int = 5) -> dict:
    """Return {position_hint, frame_data}. position_hint ∈ {top, bottom}."""
    try:
        import cv2  # type: ignore
        import mediapipe as mp  # type: ignore

        cap = cv2.VideoCapture(scene_video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            return {"position_hint": "bottom", "frames": []}
        indices = [int(i * total / max(1, samples)) for i in range(samples)]
        bottom_hits = 0
        per_frame = []
        with mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as fd:
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok:
                    continue
                h = frame.shape[0]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = fd.process(rgb)
                if not res.detections:
                    per_frame.append({"index": idx, "face": False})
                    continue
                box = res.detections[0].location_data.relative_bounding_box
                cy = (box.ymin + box.height / 2.0) * h
                if cy / h > 0.66:
                    bottom_hits += 1
                per_frame.append({"index": idx, "face": True, "cy_norm": cy / h})
        cap.release()
        position = "top" if bottom_hits >= 3 else "bottom"
        return {"position_hint": position, "frames": per_frame}
    except Exception:
        return {"position_hint": "bottom", "frames": []}
