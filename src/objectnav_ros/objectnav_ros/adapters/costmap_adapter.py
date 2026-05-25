from __future__ import annotations

from dataclasses import dataclass

from nav_msgs.msg import OccupancyGrid as RosOccupancyGrid

from objectnav_core.mapping.grid import CellState, OccupancyGrid


@dataclass(frozen=True)
class CostmapConversionConfig:
    free_threshold: int = 25
    occupied_threshold: int = 65
    unknown_value: int = -1

    def __post_init__(self) -> None:
        if self.free_threshold >= self.occupied_threshold:
            raise ValueError("free_threshold must be less than occupied_threshold")


def occupancy_grid_to_core_grid(
    message: RosOccupancyGrid,
    config: CostmapConversionConfig | None = None,
) -> OccupancyGrid:
    conversion = config or CostmapConversionConfig()
    width = int(message.info.width)
    height = int(message.info.height)
    resolution = float(message.info.resolution)
    if width <= 0 or height <= 0:
        raise ValueError("OccupancyGrid width and height must be positive")
    if resolution <= 0:
        raise ValueError("OccupancyGrid resolution must be positive")
    if len(message.data) != width * height:
        raise ValueError(
            f"OccupancyGrid data length {len(message.data)} does not match {width}x{height}"
        )

    grid = OccupancyGrid(
        width_m=width * resolution,
        height_m=height * resolution,
        resolution_m=resolution,
    )
    for row in range(height):
        for col in range(width):
            value = int(message.data[row * width + col])
            grid.set_cell(col, row, cell_state_from_occupancy_value(value, conversion))
    return grid


def core_grid_to_occupancy_grid_msg(
    grid: OccupancyGrid,
    *,
    frame_id: str,
    stamp: object | None = None,
) -> RosOccupancyGrid:
    message = RosOccupancyGrid()
    message.header.frame_id = frame_id
    if stamp is not None:
        message.header.stamp = stamp
    message.info.width = grid.width_cells
    message.info.height = grid.height_cells
    message.info.resolution = float(grid.resolution_m)
    message.info.origin.position.x = 0.0
    message.info.origin.position.y = 0.0
    message.info.origin.position.z = 0.0
    message.info.origin.orientation.w = 1.0
    message.data = [
        occupancy_value_from_cell_state(grid.get_cell(col, row))
        for row in range(grid.height_cells)
        for col in range(grid.width_cells)
    ]
    return message


def cell_state_from_occupancy_value(
    value: int,
    config: CostmapConversionConfig | None = None,
) -> CellState:
    conversion = config or CostmapConversionConfig()
    if value == conversion.unknown_value:
        return CellState.UNKNOWN
    if value <= conversion.free_threshold:
        return CellState.FREE
    if value >= conversion.occupied_threshold:
        return CellState.OCCUPIED
    return CellState.UNKNOWN


def occupancy_value_from_cell_state(state: CellState) -> int:
    if state is CellState.FREE:
        return 0
    if state is CellState.OCCUPIED:
        return 100
    return -1
