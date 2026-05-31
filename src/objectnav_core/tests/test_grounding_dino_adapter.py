import sys

import numpy as np

from objectnav_core.perception.grounding_dino_adapter import GroundingDinoDetector
from objectnav_core.perception.yolo_world_adapter import Detection


class _FakeTensor:
    def __init__(self, values: object) -> None:
        self.values = np.asarray(values)

    def cpu(self) -> "_FakeTensor":
        return self

    def numpy(self) -> np.ndarray:
        return self.values


class _FakeInputs(dict):
    def to(self, device: str) -> "_FakeInputs":
        self["device"] = device
        return self


class _FakeProcessor:
    expected_target_sizes = [(8, 8)]

    def __init__(self) -> None:
        self.text: str | None = None
        self.images_seen = 0

    def __call__(
        self,
        *,
        images: object,
        text: str,
        return_tensors: str,
    ) -> _FakeInputs:
        self.images_seen += 1
        self.text = text
        return _FakeInputs({"pixel_values": "unused", "input_ids": "unused"})

    def post_process_grounded_object_detection(
        self,
        outputs: object,
        input_ids: object,
        box_threshold: float,
        text_threshold: float,
        target_sizes: list[tuple[int, int]],
    ) -> list[dict[str, object]]:
        assert box_threshold == 0.25
        assert text_threshold == 0.2
        assert target_sizes == self.expected_target_sizes
        return [
            {
                "boxes": _FakeTensor(
                    [
                        [1.2, 2.0, 4.8, 5.1],
                        [0.0, 0.0, 2.0, 2.0],
                    ]
                ),
                "scores": _FakeTensor([0.91, 0.8]),
                "labels": ["chair", "unrelated"],
            }
        ]


class _FakeNewProcessor(_FakeProcessor):
    def post_process_grounded_object_detection(
        self,
        outputs: object,
        input_ids: object,
        threshold: float,
        text_threshold: float,
        target_sizes: list[tuple[int, int]],
    ) -> list[dict[str, object]]:
        assert threshold == 0.25
        assert text_threshold == 0.2
        assert target_sizes == [(8, 8)]
        return [
            {
                "boxes": _FakeTensor([[1.2, 2.0, 4.8, 5.1]]),
                "scores": _FakeTensor([0.91]),
                "labels": [0],
                "text_labels": ["chair"],
            }
        ]


class _FakeTvProcessor(_FakeProcessor):
    def post_process_grounded_object_detection(
        self,
        outputs: object,
        input_ids: object,
        box_threshold: float,
        text_threshold: float,
        target_sizes: list[tuple[int, int]],
    ) -> list[dict[str, object]]:
        assert box_threshold == 0.25
        assert text_threshold == 0.2
        assert target_sizes == [(8, 8)]
        return [
            {
                "boxes": _FakeTensor([[1.0, 2.0, 5.0, 6.0]]),
                "scores": _FakeTensor([0.88]),
                "labels": ["tv monitor"],
            }
        ]


class _FakeModel:
    def __init__(self) -> None:
        self.device: str | None = None
        self.called = False

    def to(self, device: str) -> "_FakeModel":
        self.device = device
        return self

    def eval(self) -> "_FakeModel":
        return self

    def __call__(self, **kwargs: object) -> object:
        self.called = True
        assert kwargs["device"] == "cpu"
        return object()


class _FakeTorch:
    def __init__(self) -> None:
        self.entered = False

    class _NoGrad:
        def __init__(self, owner: "_FakeTorch") -> None:
            self.owner = owner

        def __enter__(self) -> None:
            self.owner.entered = True

        def __exit__(self, *args: object) -> None:
            return None

    def no_grad(self) -> "_NoGrad":
        return self._NoGrad(self)


def test_importing_grounding_dino_adapter_does_not_import_transformers() -> None:
    assert "transformers" not in sys.modules


def test_grounding_dino_adapter_forwards_fake_backend_detections() -> None:
    processor = _FakeProcessor()
    model = _FakeModel()
    detector = GroundingDinoDetector(
        model_id="unused",
        categories=["chair", "plant"],
        conf=0.25,
        text_threshold=0.2,
        device="cpu",
        processor=processor,
        model=model,
    )

    detections = detector.detect(np.zeros((8, 8, 3), dtype=np.uint8))

    assert processor.text == "chair. plant."
    assert model.called is True
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


def test_grounding_dino_adapter_maps_objectnav_aliases_to_canonical_labels() -> None:
    processor = _FakeTvProcessor()
    detector = GroundingDinoDetector(
        model_id="unused",
        categories=["tv_monitor"],
        conf=0.25,
        text_threshold=0.2,
        device="cpu",
        processor=processor,
        model=_FakeModel(),
    )

    detections = detector.detect(np.zeros((8, 8, 3), dtype=np.uint8))

    assert processor.text == "tv monitor. television. tv."
    assert detections == [
        Detection(
            category="tv_monitor",
            bbox=(1, 2, 5, 6),
            confidence=0.88,
            mask=detections[0].mask,
        )
    ]


def test_grounding_dino_adapter_supports_new_transformers_threshold_name() -> None:
    detector = GroundingDinoDetector(
        model_id="unused",
        categories=["chair"],
        conf=0.25,
        text_threshold=0.2,
        device="cpu",
        processor=_FakeNewProcessor(),
        model=_FakeModel(),
    )

    detections = detector.detect(np.zeros((8, 8, 3), dtype=np.uint8))

    assert detections == [
        Detection(
            category="chair",
            bbox=(1, 2, 5, 6),
            confidence=0.91,
            mask=detections[0].mask,
        )
    ]


def test_grounding_dino_adapter_rescales_boxes_from_detector_image() -> None:
    processor = _FakeProcessor()
    processor.expected_target_sizes = [(4, 4)]
    detector = GroundingDinoDetector(
        model_id="unused",
        categories=["chair"],
        conf=0.25,
        text_threshold=0.2,
        device="cpu",
        max_image_side=4,
        processor=processor,
        model=_FakeModel(),
    )

    detections = detector.detect(np.zeros((8, 8, 3), dtype=np.uint8))

    assert detections == [
        Detection(
            category="chair",
            bbox=(2, 4, 8, 8),
            confidence=0.91,
            mask=detections[0].mask,
        )
    ]
    assert detections[0].mask.shape == (8, 8)
    assert detections[0].mask[4:8, 2:8].all()


def test_grounding_dino_adapter_runs_model_under_no_grad() -> None:
    fake_torch = _FakeTorch()
    detector = GroundingDinoDetector(
        model_id="unused",
        categories=["chair"],
        conf=0.25,
        text_threshold=0.2,
        device="cpu",
        processor=_FakeProcessor(),
        model=_FakeModel(),
        torch_backend=fake_torch,
    )

    detector.detect(np.zeros((8, 8, 3), dtype=np.uint8))

    assert fake_torch.entered is True
