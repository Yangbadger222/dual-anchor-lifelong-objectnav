from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml


@dataclass(frozen=True)
class AxialNoiseParams:
    alpha: float


@dataclass(frozen=True)
class LateralNoiseParams:
    beta: float


@dataclass(frozen=True)
class HoleParams:
    zmin: float
    zmax: float
    p_drop: float


@dataclass(frozen=True)
class DepthNoiseLevel:
    axial: AxialNoiseParams
    lateral: LateralNoiseParams
    holes: HoleParams


@dataclass(frozen=True)
class DepthNoiseProfile:
    provenance: str
    target_camera: str
    references: tuple[str, ...]
    levels: dict[str, DepthNoiseLevel]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "DepthNoiseProfile":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        levels = {
            name: DepthNoiseLevel(
                axial=AxialNoiseParams(alpha=float(values["axial"]["alpha"])),
                lateral=LateralNoiseParams(beta=float(values["lateral"]["beta"])),
                holes=HoleParams(
                    zmin=float(values["holes"]["zmin"]),
                    zmax=float(values["holes"]["zmax"]),
                    p_drop=float(values["holes"]["p_drop"]),
                ),
            )
            for name, values in payload["levels"].items()
        }
        return cls(
            provenance=str(payload["provenance"]),
            target_camera=str(payload["target_camera"]),
            references=tuple(str(item) for item in payload.get("references", ())),
            levels=levels,
        )


class DepthNoisePipelineD435:
    def __init__(self, profile: DepthNoiseProfile, seed: int) -> None:
        self.profile = profile
        self.seed = int(seed)

    def apply(
        self,
        depth: np.ndarray,
        *,
        level: str,
        surface_normals: np.ndarray | None = None,
        frame_index: int = 0,
    ) -> np.ndarray:
        if level not in self.profile.levels:
            raise KeyError(f"Unknown depth noise level: {level}")
        level_cfg = self.profile.levels[level]
        depth_f = _validate_depth(depth)
        if _is_identity(level_cfg):
            return depth_f.copy()
        rng = _rng_for(self.seed, level, frame_index)
        noisy = depth_f.copy()
        finite = np.isfinite(noisy)
        noisy[finite] += rng.normal(
            loc=0.0,
            scale=level_cfg.axial.alpha * np.square(noisy[finite]),
            size=int(finite.sum()),
        ).astype(np.float32)
        finite = np.isfinite(noisy)
        lateral_sigma = _lateral_sigma(noisy, level_cfg.lateral, surface_normals)
        noisy[finite] += rng.normal(
            loc=0.0,
            scale=lateral_sigma[finite],
            size=int(finite.sum()),
        ).astype(np.float32)
        holes = _hole_mask(noisy, level_cfg.holes, rng)
        noisy[holes] = np.nan
        noisy[np.isfinite(noisy)] = np.maximum(noisy[np.isfinite(noisy)], 1e-4)
        return noisy.astype(np.float32)


def _validate_depth(depth: np.ndarray) -> np.ndarray:
    array = np.asarray(depth)
    if array.ndim != 2:
        raise ValueError("Depth image must have shape [H, W]")
    return array.astype(np.float32, copy=False)


def _is_identity(level: DepthNoiseLevel) -> bool:
    return (
        level.axial.alpha == 0.0
        and level.lateral.beta == 0.0
        and level.holes.p_drop == 0.0
        and level.holes.zmin <= 0.1
        and level.holes.zmax >= 10.0
    )


def _rng_for(seed: int, level: str, frame_index: int) -> np.random.Generator:
    level_offset = sum((index + 1) * ord(char) for index, char in enumerate(level))
    return np.random.default_rng(seed + level_offset + frame_index * 1009)


def _lateral_sigma(
    depth: np.ndarray,
    params: LateralNoiseParams,
    surface_normals: np.ndarray | None,
) -> np.ndarray:
    if params.beta == 0.0:
        return np.zeros_like(depth, dtype=np.float32)
    cos_theta = _cos_incidence(depth, surface_normals)
    finite_depth = np.nan_to_num(depth, nan=0.0, posinf=0.0, neginf=0.0)
    return (params.beta * finite_depth / np.maximum(cos_theta, 0.2)).astype(np.float32)


def _cos_incidence(
    depth: np.ndarray,
    surface_normals: np.ndarray | None,
) -> np.ndarray:
    if surface_normals is not None:
        normals = np.asarray(surface_normals, dtype=np.float32)
        if normals.shape[:2] != depth.shape or normals.shape[2] != 3:
            raise ValueError("surface_normals must have shape [H, W, 3]")
        return np.abs(normals[:, :, 2]).clip(0.0, 1.0)
    filled = np.nan_to_num(depth, nan=float(np.nanmedian(depth)))
    gy, gx = np.gradient(filled)
    slope = np.sqrt(np.square(gx) + np.square(gy))
    return (1.0 / np.sqrt(1.0 + np.square(slope))).astype(np.float32)


def _hole_mask(
    depth: np.ndarray,
    params: HoleParams,
    rng: np.random.Generator,
) -> np.ndarray:
    invalid_range = ~np.isfinite(depth) | (depth < params.zmin) | (depth > params.zmax)
    if params.p_drop <= 0.0:
        return invalid_range
    random_drop = rng.random(depth.shape) < params.p_drop
    return invalid_range | random_drop
