from __future__ import annotations

import numpy as np
import pytest

from objectnav_core.evaluation.habitat_pointnav_ddppo_backend import (
    _prepare_ddppo_depth_observation,
)


def test_prepare_ddppo_depth_observation_accepts_normalized_hxw_depth() -> None:
    depth = np.array([[0.0, 0.25], [0.75, 1.0]], dtype=np.float32)

    prepared = _prepare_ddppo_depth_observation(depth)

    assert prepared.shape == (256, 256, 1)
    assert prepared.dtype == np.float32
    assert prepared[0, 0, 0] == pytest.approx(0.0)
    assert prepared[-1, -1, 0] == pytest.approx(1.0)


def test_prepare_ddppo_depth_observation_accepts_hxwx1_depth() -> None:
    depth = np.full((3, 2, 1), 0.25, dtype=np.float32)

    prepared = _prepare_ddppo_depth_observation(depth)

    assert prepared.shape == (256, 256, 1)
    assert float(prepared.mean()) == pytest.approx(0.25)


def test_prepare_ddppo_depth_observation_normalizes_meter_depth() -> None:
    depth = np.full((2, 2), 5.0, dtype=np.float32)

    prepared = _prepare_ddppo_depth_observation(depth, max_depth_m=10.0)

    assert prepared.shape == (256, 256, 1)
    assert float(prepared.mean()) == pytest.approx(0.5)


def test_prepare_ddppo_depth_observation_rejects_multi_channel_depth() -> None:
    with pytest.raises(ValueError, match="single-channel depth"):
        _prepare_ddppo_depth_observation(np.zeros((2, 2, 2), dtype=np.float32))
