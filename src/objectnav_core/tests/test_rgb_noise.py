from pathlib import Path

import numpy as np

from objectnav_core.simulation.rgb_noise import (
    AgentMotion,
    RgbNoisePipeline,
    RgbNoiseProfile,
)


def test_clean_rgb_noise_level_is_identity(tmp_path: Path) -> None:
    profile = RgbNoiseProfile.from_yaml("configs/noise/rgb_published_v1.yaml")
    pipeline = RgbNoisePipeline(profile=profile, seed=7)
    rgb = np.arange(4 * 5 * 3, dtype=np.uint8).reshape(4, 5, 3)

    noisy = pipeline.apply(
        rgb,
        agent_motion=AgentMotion(translation_m=0.0, rotation_rad=0.0),
        level="clean",
    )

    assert noisy.dtype == np.uint8
    assert noisy.shape == rgb.shape
    np.testing.assert_array_equal(noisy, rgb)


def test_rgb_noise_is_deterministic_for_seed_and_frame() -> None:
    profile = RgbNoiseProfile.from_yaml("configs/noise/rgb_published_v1.yaml")
    rgb = np.full((8, 8, 3), 128, dtype=np.uint8)
    motion = AgentMotion(translation_m=0.25, rotation_rad=0.0)

    first = RgbNoisePipeline(profile=profile, seed=11).apply(
        rgb,
        agent_motion=motion,
        level="heavy",
        frame_index=3,
    )
    second = RgbNoisePipeline(profile=profile, seed=11).apply(
        rgb,
        agent_motion=motion,
        level="heavy",
        frame_index=3,
    )

    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, rgb)


def test_motion_blur_spreads_bright_pixel_when_agent_moves() -> None:
    profile = RgbNoiseProfile.from_yaml("configs/noise/rgb_published_v1.yaml")
    rgb = np.zeros((9, 9, 3), dtype=np.uint8)
    rgb[4, 4] = 255

    noisy = RgbNoisePipeline(profile=profile, seed=19).apply(
        rgb,
        agent_motion=AgentMotion(translation_m=0.25, rotation_rad=0.0),
        level="mild",
    )

    assert noisy[4, 4, 0] < 255
    assert (noisy[4, :, 0] > 0).sum() >= 5
