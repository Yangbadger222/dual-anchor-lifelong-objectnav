from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np


@dataclass(frozen=True, eq=False)
class Detection:
    category: str
    bbox: tuple[int, int, int, int]
    confidence: float
    mask: np.ndarray

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Detection):
            return False
        return (
            self.category == other.category
            and self.bbox == other.bbox
            and self.confidence == other.confidence
            and np.array_equal(self.mask, other.mask)
        )


class YoloWorldDetector:
    def __init__(
        self,
        *,
        weights: str,
        categories: list[str],
        conf: float = 0.25,
        device: str = "auto",
        model: Any | None = None,
    ) -> None:
        if not categories:
            raise ValueError("categories must not be empty")
        if not 0.0 <= conf <= 1.0:
            raise ValueError("conf must be in [0, 1]")
        self.weights = weights
        self.categories = list(categories)
        self.conf = float(conf)
        self.device = device
        self.model = model if model is not None else self._load_model(weights)
        if hasattr(self.model, "set_classes"):
            self.model.set_classes(self.categories)

    def detect(self, rgb: np.ndarray) -> list[Detection]:
        image = _validate_rgb(rgb)
        predict_kwargs: dict[str, Any] = {"conf": self.conf, "verbose": False}
        if self.device != "auto":
            predict_kwargs["device"] = self.device
        results = self.model.predict(image, **predict_kwargs)
        detections: list[Detection] = []
        for result in results:
            detections.extend(_detections_from_result(result, image.shape[:2], self))
        return detections

    @staticmethod
    def _load_model(weights: str) -> Any:
        try:
            from ultralytics import YOLOWorld
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "ultralytics is required for YOLO-World detection. Install it in "
                "the habitat environment or use a test backend."
            ) from exc
        return YOLOWorld(weights)


def _validate_rgb(rgb: np.ndarray) -> np.ndarray:
    array = np.asarray(rgb)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("RGB image must have shape [H, W, 3]")
    if array.dtype != np.uint8:
        raise ValueError("RGB image must have dtype uint8")
    return array


def _detections_from_result(
    result: Any,
    image_shape: tuple[int, int],
    detector: YoloWorldDetector,
) -> list[Detection]:
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []
    xyxy_values = _as_numpy(getattr(boxes, "xyxy", []))
    conf_values = _as_numpy(getattr(boxes, "conf", []))
    cls_values = _as_numpy(getattr(boxes, "cls", []))
    detections: list[Detection] = []
    for xyxy, confidence, class_id in zip(xyxy_values, conf_values, cls_values):
        confidence_float = float(confidence)
        if confidence_float < detector.conf:
            continue
        category = _category_name(result, detector.categories, int(class_id))
        if category not in detector.categories:
            continue
        bbox = _clip_bbox(xyxy, image_shape)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue
        detections.append(
            Detection(
                category=category,
                bbox=bbox,
                confidence=round(confidence_float, 6),
                mask=_bbox_mask(image_shape, bbox),
            )
        )
    return detections


def _as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def _category_name(result: Any, categories: list[str], class_id: int) -> str:
    names = getattr(result, "names", None)
    if isinstance(names, dict) and class_id in names:
        return str(names[class_id])
    if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
        return str(names[class_id])
    if 0 <= class_id < len(categories):
        return categories[class_id]
    return str(class_id)


def _clip_bbox(
    xyxy: Iterable[float],
    image_shape: tuple[int, int],
) -> tuple[int, int, int, int]:
    height, width = image_shape
    x1, y1, x2, y2 = [float(value) for value in xyxy]
    return (
        max(0, min(width, int(np.floor(x1)))),
        max(0, min(height, int(np.floor(y1)))),
        max(0, min(width, int(np.ceil(x2)))),
        max(0, min(height, int(np.ceil(y2)))),
    )


def _bbox_mask(image_shape: tuple[int, int], bbox: tuple[int, int, int, int]) -> np.ndarray:
    height, width = image_shape
    mask = np.zeros((height, width), dtype=bool)
    x1, y1, x2, y2 = bbox
    mask[y1:y2, x1:x2] = True
    return mask
