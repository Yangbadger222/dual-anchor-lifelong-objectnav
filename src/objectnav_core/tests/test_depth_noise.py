import numpy as np

from objectnav_core.simulation.depth_noise import (
    DepthNoisePipelineD435,
    DepthNoiseProfile,
)


def test_clean_depth_noise_level_is_identity() -> None:
    profile = DepthNoiseProfile.from_yaml("configs/noise/depth_realsense_d435_v1.yaml")
    pipeline = DepthNoisePipelineD435(profile=profile, seed=5)
    depth = np.array([[0.4, 1.0], [2.0, np.nan]], dtype=np.float32)

    noisy = pipeline.apply(depth, level="clean")

    assert noisy.dtype == np.float32
    np.testing.assert_array_equal(noisy, depth)


def test_depth_noise_is_deterministic_and_marks_holes_as_nan() -> None:
    profile = DepthNoiseProfile.from_yaml("configs/noise/depth_realsense_d435_v1.yaml")
    depth = np.array(
        [
            [0.1, 0.5, 1.5],
            [2.5, 3.5, 5.0],
        ],
        dtype=np.float32,
    )

    first = DepthNoisePipelineD435(profile=profile, seed=23).apply(
        depth,
        level="heavy",
        frame_index=4,
    )
    second = DepthNoisePipelineD435(profile=profile, seed=23).apply(
        depth,
        level="heavy",
        frame_index=4,
    )

    np.testing.assert_array_equal(first, second)
    assert np.isnan(first[0, 0])
    assert np.isnan(first[1, 1])
    assert np.isnan(first[1, 2])
    assert not np.any(first[np.isfinite(first)] == 0.0)


def test_depth_noise_rejects_unknown_level() -> None:
    profile = DepthNoiseProfile.from_yaml("configs/noise/depth_realsense_d435_v1.yaml")
    pipeline = DepthNoisePipelineD435(profile=profile, seed=5)

    try:
        pipeline.apply(np.ones((2, 2), dtype=np.float32), level="medium")
    except KeyError as exc:
        assert "medium" in str(exc)
    else:
        raise AssertionError("unknown depth level should fail")
