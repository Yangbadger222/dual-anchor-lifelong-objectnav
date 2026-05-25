import pytest
from nav_msgs.msg import OccupancyGrid as RosOccupancyGrid

from objectnav_core.mapping.grid import CellState
from objectnav_ros.adapters.costmap_adapter import (
    CostmapConversionConfig,
    cell_state_from_occupancy_value,
    core_grid_to_occupancy_grid_msg,
    occupancy_grid_to_core_grid,
)


def test_occupancy_grid_to_core_grid_maps_thresholds() -> None:
    message = RosOccupancyGrid()
    message.info.width = 3
    message.info.height = 2
    message.info.resolution = 0.5
    message.data = [-1, 0, 100, 20, 50, 70]

    grid = occupancy_grid_to_core_grid(message)

    assert grid.width_m == pytest.approx(1.5)
    assert grid.height_m == pytest.approx(1.0)
    assert grid.resolution_m == pytest.approx(0.5)
    assert grid.get_cell(0, 0) is CellState.UNKNOWN
    assert grid.get_cell(1, 0) is CellState.FREE
    assert grid.get_cell(2, 0) is CellState.OCCUPIED
    assert grid.get_cell(0, 1) is CellState.FREE
    assert grid.get_cell(1, 1) is CellState.UNKNOWN
    assert grid.get_cell(2, 1) is CellState.OCCUPIED


def test_occupancy_grid_rejects_wrong_data_length() -> None:
    message = RosOccupancyGrid()
    message.info.width = 2
    message.info.height = 2
    message.info.resolution = 0.5
    message.data = [0, 0, 0]

    with pytest.raises(ValueError, match="data length"):
        occupancy_grid_to_core_grid(message)


def test_cell_state_thresholds_are_configurable() -> None:
    config = CostmapConversionConfig(
        free_threshold=10,
        occupied_threshold=90,
        unknown_value=-2,
    )

    assert cell_state_from_occupancy_value(-2, config) is CellState.UNKNOWN
    assert cell_state_from_occupancy_value(10, config) is CellState.FREE
    assert cell_state_from_occupancy_value(50, config) is CellState.UNKNOWN
    assert cell_state_from_occupancy_value(90, config) is CellState.OCCUPIED


def test_core_grid_to_occupancy_grid_msg_preserves_dimensions_and_values() -> None:
    grid = occupancy_grid_to_core_grid(_ros_grid(width=2, height=2, data=[-1, 0, 100, 50]))

    message = core_grid_to_occupancy_grid_msg(grid, frame_id="map")

    assert message.header.frame_id == "map"
    assert message.info.width == 2
    assert message.info.height == 2
    assert message.info.resolution == pytest.approx(0.5)
    assert list(message.data) == [-1, 0, 100, -1]


def _ros_grid(width: int, height: int, data: list[int]) -> RosOccupancyGrid:
    message = RosOccupancyGrid()
    message.info.width = width
    message.info.height = height
    message.info.resolution = 0.5
    message.data = data
    return message
