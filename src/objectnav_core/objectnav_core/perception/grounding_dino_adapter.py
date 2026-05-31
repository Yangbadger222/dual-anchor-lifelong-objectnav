from __future__ import annotations

import inspect
from typing import Any

import numpy as np
from PIL import Image

from objectnav_core.perception.yolo_world_adapter import (
    Detection,
    _as_numpy,
    _bbox_mask,
    _clip_bbox,
    _validate_rgb,
)


DEFAULT_GROUNDING_DINO_MODEL = "IDEA-Research/grounding-dino-tiny"
_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "tv_monitor": ("tv monitor", "television", "tv"),
}


class GroundingDinoDetector:
    def __init__(
        self,
        *,
        model_id: str = DEFAULT_GROUNDING_DINO_MODEL,
        categories: list[str],
        conf: float = 0.25,
        text_threshold: float = 0.25,
        max_image_side: int | None = None,
        device: str = "auto",
        processor: Any | None = None,
        model: Any | None = None,
        torch_backend: Any | None = None,
    ) -> None:
        if not categories:
            raise ValueError("categories must not be empty")
        if not 0.0 <= conf <= 1.0:
            raise ValueError("conf must be in [0, 1]")
        if not 0.0 <= text_threshold <= 1.0:
            raise ValueError("text_threshold must be in [0, 1]")
        if max_image_side is not None and max_image_side <= 0:
            raise ValueError("max_image_side must be positive when provided")
        self.model_id = model_id
        self.categories = list(categories)
        self.conf = float(conf)
        self.text_threshold = float(text_threshold)
        self.max_image_side = max_image_side
        self.device = _resolve_device(device)
        self._torch = (
            torch_backend
            if torch_backend is not None
            else _load_torch_or_noop(require_torch=processor is None or model is None)
        )
        if processor is None or model is None:
            loaded_processor, loaded_model = self._load_backend(model_id)
            processor = loaded_processor if processor is None else processor
            model = loaded_model if model is None else model
        self.processor = processor
        self.model = model
        if hasattr(self.model, "to"):
            self.model = self.model.to(self.device)
        if hasattr(self.model, "eval"):
            self.model.eval()

    def detect(self, rgb: np.ndarray) -> list[Detection]:
        image = _validate_rgb(rgb)
        detector_image, scale_x, scale_y = _resize_for_detector(
            image,
            max_image_side=self.max_image_side,
        )
        inputs = self.processor(
            images=Image.fromarray(detector_image),
            text=_prompt_text(self.categories),
            return_tensors="pt",
        )
        if hasattr(inputs, "to"):
            inputs = inputs.to(self.device)
        with self._torch.no_grad():
            outputs = self.model(**inputs)
        input_ids = inputs.get("input_ids") if isinstance(inputs, dict) else None
        results = _post_process_grounded_object_detection(
            processor=self.processor,
            outputs=outputs,
            input_ids=input_ids,
            conf=self.conf,
            text_threshold=self.text_threshold,
            target_sizes=[detector_image.shape[:2]],
        )
        return _detections_from_grounding_result(
            result=results[0] if results else {},
            image_shape=image.shape[:2],
            scale_x=scale_x,
            scale_y=scale_y,
            categories=self.categories,
            conf=self.conf,
        )

    @staticmethod
    def _load_backend(model_id: str) -> tuple[Any, Any]:
        try:
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "transformers is required for Grounding-DINO detection. Install "
                "transformers, safetensors, pillow, and compatible torch packages "
                "in the habitat environment or use a test backend."
            ) from exc
        processor = AutoProcessor.from_pretrained(model_id)
        model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id)
        return processor, model


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    try:
        torch = _load_torch()
    except ModuleNotFoundError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_torch() -> Any:
    import torch

    return torch


def _load_torch_or_noop(*, require_torch: bool) -> Any:
    try:
        return _load_torch()
    except ModuleNotFoundError:
        if require_torch:
            raise
        return _NoopTorch()


class _NoopTorch:
    class _NoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: object) -> None:
            return None

    def no_grad(self) -> "_NoGrad":
        return self._NoGrad()


def _prompt_text(categories: list[str]) -> str:
    labels: list[str] = []
    for category in categories:
        labels.extend(_category_prompt_labels(category))
    return " ".join(f"{label.rstrip('.')}." for label in labels)


def _detections_from_grounding_result(
    result: dict[str, Any],
    image_shape: tuple[int, int],
    *,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    categories: list[str],
    conf: float,
) -> list[Detection]:
    boxes = _as_numpy(result.get("boxes", []))
    scores = _as_numpy(result.get("scores", []))
    labels = result.get("text_labels", result.get("labels", []))
    canonical_by_label = _canonical_labels(categories)
    detections: list[Detection] = []
    for xyxy, score, label in zip(boxes, scores, labels):
        confidence = float(score)
        category = canonical_by_label.get(_normalize_label(str(label)))
        if confidence < conf or category is None:
            continue
        scaled_xyxy = _scale_xyxy(xyxy, scale_x=scale_x, scale_y=scale_y)
        bbox = _clip_bbox(scaled_xyxy, image_shape)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue
        detections.append(
            Detection(
                category=category,
                bbox=bbox,
                confidence=round(confidence, 6),
                mask=_bbox_mask(image_shape, bbox),
            )
        )
    return detections


def _category_prompt_labels(category: str) -> tuple[str, ...]:
    canonical = str(category).strip().lower()
    labels = [canonical.replace("_", " ")]
    labels.extend(_CATEGORY_ALIASES.get(canonical, ()))
    deduped: list[str] = []
    seen: set[str] = set()
    for label in labels:
        normalized = _normalize_label(label)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(label)
    return tuple(deduped)


def _canonical_labels(categories: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for category in categories:
        canonical = str(category).strip().lower()
        mapping[_normalize_label(canonical)] = canonical
        for label in _category_prompt_labels(canonical):
            mapping[_normalize_label(label)] = canonical
    return mapping


def _normalize_label(label: str) -> str:
    return " ".join(str(label).strip().lower().replace("_", " ").split())


def _resize_for_detector(
    image: np.ndarray,
    *,
    max_image_side: int | None,
) -> tuple[np.ndarray, float, float]:
    if max_image_side is None:
        return image, 1.0, 1.0
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_image_side:
        return image, 1.0, 1.0
    ratio = float(max_image_side) / float(longest)
    resized_width = max(1, int(round(width * ratio)))
    resized_height = max(1, int(round(height * ratio)))
    resized = np.asarray(
        Image.fromarray(image).resize(
            (resized_width, resized_height),
            resample=Image.Resampling.BILINEAR,
        )
    )
    return resized, width / resized_width, height / resized_height


def _scale_xyxy(
    xyxy: Any,
    *,
    scale_x: float,
    scale_y: float,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = [float(value) for value in xyxy]
    return x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y


def _post_process_grounded_object_detection(
    *,
    processor: Any,
    outputs: Any,
    input_ids: Any,
    conf: float,
    text_threshold: float,
    target_sizes: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    method = processor.post_process_grounded_object_detection
    parameters = inspect.signature(method).parameters
    threshold_kwargs: dict[str, Any]
    if "box_threshold" in parameters:
        threshold_kwargs = {"box_threshold": conf}
    else:
        threshold_kwargs = {"threshold": conf}
    return method(
        outputs,
        input_ids=input_ids,
        **threshold_kwargs,
        text_threshold=text_threshold,
        target_sizes=target_sizes,
    )
