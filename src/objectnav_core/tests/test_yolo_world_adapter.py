import sys

import numpy as np

from objectnav_core.perception.yolo_world_adapter import Detection, YoloWorldDetector


class _FakeBoxes:
    xyxy = np.array([[1.2, 2.0, 4.8, 5.1], [0.0, 0.0, 2.0, 2.0]], dtype=float)
    conf = np.array([0.91, 0.1], dtype=float)
    cls = np.array([0, 1], dtype=float)


class _FakeResult:
    boxes = _FakeBoxes()
    names = {0: "chair", 1: "plant"}


class _FakeModel:
    def __init__(self) -> None:
        self.classes: list[str] | None = None

    def set_classes(self, classes: list[str]) -> None:
        self.classes = classes

    def predict(self, rgb: np.ndarray, **kwargs: object) -> list[_FakeResult]:
        assert rgb.shape == (8, 8, 3)
        assert kwargs["conf"] == 0.25
        return [_FakeResult()]


def test_importing_detector_adapter_does_not_import_ultralytics() -> None:
    assert "ultralytics" not in sys.modules


def test_yolo_world_adapter_forwards_fake_backend_detections() -> None:
    model = _FakeModel()
    detector = YoloWorldDetector(
        weights="unused.pt",
        categories=["chair", "plant"],
        conf=0.25,
        device="cpu",
        model=model,
    )

    detections = detector.detect(np.zeros((8, 8, 3), dtype=np.uint8))

    assert model.classes == ["chair", "plant"]
    assert detections == [
        Detection(
            category="chair",
            bbox=(1, 2, 5, 6),
            confidence=0.91,
            mask=detections[0].mask,
        )
    ]
    assert detections[0].mask.dtype == bool
    assert detections[0].mask.shape == (8, 8)
    assert detections[0].mask[2:6, 1:5].all()
    assert detections[0].mask.sum() == 16
