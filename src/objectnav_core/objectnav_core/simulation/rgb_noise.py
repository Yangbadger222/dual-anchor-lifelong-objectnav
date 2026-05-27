from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import yaml


@dataclass(frozen=True)
class AgentMotion:
    translation_m: float = 0.0
    rotation_rad: float = 0.0


@dataclass(frozen=True)
class PoissonGaussianParams:
    a: float
    b: float


@dataclass(frozen=True)
class MotionBlurParams:
    t_exp_ms: float


@dataclass(frozen=True)
class JpegParams:
    q: int


@dataclass(frozen=True)
class RgbNoiseLevel:
    pg: PoissonGaussianParams
    blur: MotionBlurParams
    jpeg: JpegParams


@dataclass(frozen=True)
class RgbNoiseProfile:
    provenance: str
    references: tuple[str, ...]
    levels: dict[str, RgbNoiseLevel]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RgbNoiseProfile":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        levels = {
            name: RgbNoiseLevel(
                pg=PoissonGaussianParams(
                    a=float(values["pg"]["a"]),
                    b=float(values["pg"]["b"]),
                ),
                blur=MotionBlurParams(
                    t_exp_ms=float(values["blur"]["t_exp_ms"]),
                ),
                jpeg=JpegParams(q=int(values["jpeg"]["q"])),
            )
            for name, values in payload["levels"].items()
        }
        return cls(
            provenance=str(payload["provenance"]),
            references=tuple(str(item) for item in payload.get("references", ())),
            levels=levels,
        )


class RgbNoisePipeline:
    def __init__(self, profile: RgbNoiseProfile, seed: int) -> None:
        self.profile = profile
        self.seed = int(seed)

    def apply(
        self,
        rgb: np.ndarray,
        *,
        agent_motion: AgentMotion,
        level: str,
        frame_index: int = 0,
    ) -> np.ndarray:
        if level not in self.profile.levels:
            raise KeyError(f"Unknown RGB noise level: {level}")
        level_cfg = self.profile.levels[level]
        image = _validate_rgb(rgb)
        if _is_identity(level_cfg):
            return image.copy()
        image_f = image.astype(np.float32) / 255.0
        image_f = _apply_motion_blur(image_f, agent_motion, level_cfg.blur)
        image_f = _apply_poisson_gaussian(
            image_f,
            level_cfg.pg,
            rng=_rng_for(self.seed, level, frame_index),
        )
        image_u8 = np.clip(np.rint(image_f * 255.0), 0, 255).astype(np.uint8)
        return _apply_jpeg(image_u8, level_cfg.jpeg.q)


def _validate_rgb(rgb: np.ndarray) -> np.ndarray:
    array = np.asarray(rgb)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("RGB image must have shape [H, W, 3]")
    if array.dtype != np.uint8:
        raise ValueError("RGB image must have dtype uint8")
    return array


def _is_identity(level: RgbNoiseLevel) -> bool:
    return (
        level.pg.a == 0.0
        and level.pg.b == 0.0
        and level.blur.t_exp_ms == 0.0
        and level.jpeg.q >= 100
    )


def _rng_for(seed: int, level: str, frame_index: int) -> np.random.Generator:
    level_offset = sum((index + 1) * ord(char) for index, char in enumerate(level))
    return np.random.default_rng(seed + level_offset + frame_index * 1009)


def _apply_motion_blur(
    image: np.ndarray,
    motion: AgentMotion,
    params: MotionBlurParams,
) -> np.ndarray:
    if params.t_exp_ms <= 0.0:
        return image
    motion_score = abs(motion.translation_m) * 20.0 + abs(motion.rotation_rad) * 10.0
    if motion_score <= 0.0:
        return image
    kernel_len = int(round(motion_score * max(params.t_exp_ms, 1.0) / 15.0))
    kernel_len = max(1, min(15, kernel_len))
    if kernel_len <= 1:
        return image
    if kernel_len % 2 == 0:
        kernel_len += 1
    return _horizontal_box_blur(image, kernel_len)


def _horizontal_box_blur(image: np.ndarray, kernel_len: int) -> np.ndarray:
    pad = kernel_len // 2
    padded = np.pad(image, ((0, 0), (pad, pad), (0, 0)), mode="edge")
    blurred = np.zeros_like(image, dtype=np.float32)
    for offset in range(kernel_len):
        blurred += padded[:, offset : offset + image.shape[1], :]
    return blurred / float(kernel_len)


def _apply_poisson_gaussian(
    image: np.ndarray,
    params: PoissonGaussianParams,
    *,
    rng: np.random.Generator,
) -> np.ndarray:
    if params.a == 0.0 and params.b == 0.0:
        return image
    variance = np.maximum(params.a * image + params.b, 0.0)
    noise = rng.normal(loc=0.0, scale=np.sqrt(variance), size=image.shape)
    return np.clip(image + noise.astype(np.float32), 0.0, 1.0)


def _apply_jpeg(image: np.ndarray, quality: int) -> np.ndarray:
    if quality >= 100:
        return image
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return _quantize_without_pillow(image, quality)
    buffer = BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    return np.asarray(Image.open(buffer).convert("RGB"), dtype=np.uint8)


def _quantize_without_pillow(image: np.ndarray, quality: int) -> np.ndarray:
    step = max(1, int(round((100 - quality) / 8)))
    return (np.rint(image.astype(np.float32) / step) * step).clip(0, 255).astype(np.uint8)
