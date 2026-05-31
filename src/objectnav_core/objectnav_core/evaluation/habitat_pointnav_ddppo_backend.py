from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np


DDPPO_DEPTH_SHAPE: tuple[int, int, int] = (256, 256, 1)


class HabitatPointNavDDPPOBackend:
    """Lazy Habitat-Baselines PointNav/DDPPO adapter for TargetNav."""

    def __init__(self, *, policy: Any, torch_module: Any, device: Any) -> None:
        self.policy = policy
        self.torch = torch_module
        self.device = device
        self.hidden_states = None
        self.prev_actions = None
        self.masks = None
        self.reset()

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str | Path,
        *,
        device: str = "auto",
    ) -> "HabitatPointNavDDPPOBackend":
        torch = _import_torch()
        spaces, pointnav_policy_cls = _import_habitat_baselines_policy()
        resolved_device = _resolve_torch_device(torch, device)
        policy = _build_pointnav_policy(spaces, pointnav_policy_cls)
        checkpoint = _torch_load_checkpoint_with_legacy_config(
            torch,
            checkpoint_path,
        )
        state_dict = _extract_policy_state_dict(checkpoint)
        missing, unexpected = policy.load_state_dict(state_dict, strict=False)
        if missing or unexpected:
            raise ValueError(
                "TargetNav DDPPO checkpoint is incompatible with "
                f"PointNavResNetPolicy: missing={list(missing)}, "
                f"unexpected={list(unexpected)}"
            )
        policy.to(resolved_device)
        policy.eval()
        return cls(policy=policy, torch_module=torch, device=resolved_device)

    def reset(self) -> None:
        shape = (1, *self.policy.hidden_state_shape)
        self.hidden_states = self.torch.zeros(
            shape,
            dtype=self.torch.float32,
            device=self.device,
        )
        self.prev_actions = self.torch.zeros(
            (1, 1),
            dtype=self.torch.long,
            device=self.device,
        )
        self.masks = self.torch.zeros(
            (1, 1),
            dtype=self.torch.bool,
            device=self.device,
        )

    def act(
        self,
        *,
        depth: Any,
        pointgoal_with_gps_compass: Any,
    ) -> int:
        depth_observation = _prepare_ddppo_depth_observation(depth)
        pointgoal = np.asarray(pointgoal_with_gps_compass, dtype=np.float32)
        if pointgoal.shape != (2,):
            raise ValueError("pointgoal_with_gps_compass must have shape (2,)")
        observations = {
            "depth": self.torch.from_numpy(depth_observation)
            .unsqueeze(0)
            .to(self.device),
            "pointgoal_with_gps_compass": self.torch.from_numpy(pointgoal)
            .unsqueeze(0)
            .to(self.device),
        }
        with self.torch.no_grad():
            action_data = self.policy.act(
                observations,
                self.hidden_states,
                self.prev_actions,
                self.masks,
                deterministic=True,
            )
        self.hidden_states = action_data.rnn_hidden_states
        action_id = int(action_data.actions.reshape(-1)[0].item())
        self.prev_actions.fill_(action_id)
        self.masks.fill_(True)
        return action_id


def _prepare_ddppo_depth_observation(
    depth: Any,
    *,
    output_shape: tuple[int, int, int] = DDPPO_DEPTH_SHAPE,
    max_depth_m: float = 10.0,
) -> np.ndarray:
    array = np.asarray(depth, dtype=np.float32)
    if array.ndim == 2:
        depth_2d = array
    elif array.ndim == 3 and array.shape[2] == 1:
        depth_2d = array[:, :, 0]
    else:
        raise ValueError("DDPPO backend requires single-channel depth")
    if depth_2d.size == 0:
        raise ValueError("DDPPO backend requires non-empty depth")
    finite = depth_2d[np.isfinite(depth_2d)]
    if finite.size == 0:
        raise ValueError("DDPPO backend requires finite depth values")
    normalized = float(np.nanmax(finite)) <= 1.0
    clean = np.nan_to_num(depth_2d, nan=0.0, posinf=max_depth_m, neginf=0.0)
    if normalized:
        clean = np.clip(clean, 0.0, 1.0)
    else:
        if max_depth_m <= 0.0:
            raise ValueError("max_depth_m must be positive")
        clean = np.clip(clean / float(max_depth_m), 0.0, 1.0)
    output_height, output_width, output_channels = output_shape
    if output_channels != 1:
        raise ValueError("DDPPO depth output must be single-channel")
    resized = _resize_nearest_2d(clean, height=output_height, width=output_width)
    return resized[:, :, None].astype(np.float32, copy=False)


def _resize_nearest_2d(array: np.ndarray, *, height: int, width: int) -> np.ndarray:
    if height <= 0 or width <= 0:
        raise ValueError("output height and width must be positive")
    source_height, source_width = array.shape
    row_indices = np.rint(np.linspace(0, source_height - 1, height)).astype(np.int64)
    col_indices = np.rint(np.linspace(0, source_width - 1, width)).astype(np.int64)
    return array[row_indices[:, None], col_indices[None, :]]


def _import_torch() -> Any:
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - local unit tests avoid torch.
        raise RuntimeError(
            "PyTorch is required for the TargetNav DDPPO backend. Run this in "
            "the Linux conda habitat environment."
        ) from exc
    return torch


def _import_habitat_baselines_policy() -> tuple[Any, Any]:
    try:
        from gym import spaces  # type: ignore[import-not-found]
        from habitat_baselines.rl.ddppo.policy import (  # type: ignore[import-not-found]
            PointNavResNetPolicy,
        )
    except ImportError as exc:  # pragma: no cover - exercised in Linux runtime.
        raise RuntimeError(
            "habitat-baselines is required for the TargetNav DDPPO backend. "
            "Install it with `pip install -e third_party/habitat-lab/habitat-baselines`."
        ) from exc
    return spaces, PointNavResNetPolicy


def _resolve_torch_device(torch: Any, requested: str) -> Any:
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    return torch.device(requested)


def _build_pointnav_policy(spaces: Any, pointnav_policy_cls: Any) -> Any:
    observation_space = spaces.Dict(
        {
            "depth": spaces.Box(
                low=0.0,
                high=1.0,
                shape=DDPPO_DEPTH_SHAPE,
                dtype=np.float32,
            ),
            "pointgoal_with_gps_compass": spaces.Box(
                low=np.array([0.0, -np.pi], dtype=np.float32),
                high=np.array([np.inf, np.pi], dtype=np.float32),
                dtype=np.float32,
            ),
        }
    )
    action_space = spaces.Discrete(4)
    return pointnav_policy_cls(
        observation_space=observation_space,
        action_space=action_space,
        hidden_size=512,
        num_recurrent_layers=2,
        rnn_type="LSTM",
        backbone="resnet50",
        normalize_visual_inputs=False,
    )


def _torch_load_checkpoint_with_legacy_config(
    torch: Any,
    checkpoint_path: str | Path,
) -> Mapping[str, Any]:
    _install_legacy_habitat_config_shim()
    try:
        checkpoint = torch.load(
            Path(checkpoint_path),
            map_location="cpu",
            weights_only=False,
        )
    except TypeError:
        checkpoint = torch.load(Path(checkpoint_path), map_location="cpu")
    if not isinstance(checkpoint, Mapping):
        raise ValueError("TargetNav DDPPO checkpoint must be a mapping")
    return checkpoint


def _install_legacy_habitat_config_shim() -> None:
    try:
        import habitat.config.default as habitat_default  # type: ignore[import-not-found]
    except ImportError:
        return
    if hasattr(habitat_default, "Config"):
        return

    class Config(dict):
        def __getattr__(self, name: str) -> Any:
            try:
                return self[name]
            except KeyError as exc:
                raise AttributeError(name) from exc

        def __setattr__(self, name: str, value: Any) -> None:
            self[name] = value

        def clone(self) -> "Config":
            return Config(self)

        def freeze(self) -> None:
            return None

        def defrost(self) -> None:
            return None

    Config.__module__ = "habitat.config.default"
    setattr(habitat_default, "Config", Config)


def _extract_policy_state_dict(checkpoint: Mapping[str, Any]) -> Mapping[str, Any]:
    raw_state = checkpoint.get("state_dict", checkpoint)
    if not isinstance(raw_state, Mapping):
        raise ValueError("TargetNav DDPPO checkpoint does not contain a state_dict")
    stripped = {}
    for key, value in raw_state.items():
        clean_key = str(key)
        for prefix in ("module.", "actor_critic."):
            if clean_key.startswith(prefix):
                clean_key = clean_key[len(prefix) :]
        stripped[clean_key] = value
    return stripped
