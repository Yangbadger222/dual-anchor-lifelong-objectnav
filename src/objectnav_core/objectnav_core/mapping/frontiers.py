from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import Pose2D


@dataclass(frozen=True)
class FrontierCluster:
    cells: tuple[tuple[int, int], ...]
    centroid: Pose2D


def extract_frontier_clusters(grid: OccupancyGrid) -> list[FrontierCluster]:
    frontier_cells: set[tuple[int, int]] = set()
    for row in range(grid.height_cells):
        for col in range(grid.width_cells):
            if not grid.is_unknown_cell(col, row):
                continue
            if any(
                grid.is_free_cell(col + dc, row + dr)
                for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ):
                frontier_cells.add((col, row))

    clusters: list[FrontierCluster] = []
    while frontier_cells:
        start = frontier_cells.pop()
        queue: deque[tuple[int, int]] = deque([start])
        cells = [start]
        while queue:
            col, row = queue.popleft()
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (col + dc, row + dr)
                if neighbor in frontier_cells:
                    frontier_cells.remove(neighbor)
                    queue.append(neighbor)
                    cells.append(neighbor)
        xs, ys = zip(*(grid.cell_center(col, row) for col, row in cells), strict=True)
        clusters.append(
            FrontierCluster(
                cells=tuple(sorted(cells)),
                centroid=Pose2D(x=sum(xs) / len(xs), y=sum(ys) / len(ys)),
            )
        )
    clusters.sort(key=lambda cluster: (cluster.centroid.x, cluster.centroid.y))
    return clusters

