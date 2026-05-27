from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


DEFAULT_FORWARD_ACTIONS: tuple[str, ...] = (
    "move_forward",
    "turn_left",
    "move_forward",
    "turn_right",
    "move_forward",
)

TURN_AROUND: tuple[str, str] = ("turn_left", "turn_left")

TURN_INVERSES = {
    "turn_left": "turn_right",
    "turn_right": "turn_left",
}


def invert_habitat_actions(actions: Sequence[str]) -> tuple[str, ...]:
    """Return a simple Habitat action sequence that retraces a forward plan.

    Habitat's default action space has no `move_backward`, so the caller is
    expected to turn around before and after this inverse sequence. Forward
    moves remain forward moves, while turns swap direction in reverse order.
    """

    inverse: list[str] = []
    for action in reversed(tuple(actions)):
        inverse.append(TURN_INVERSES.get(action, action))
    return tuple(inverse)


@dataclass(frozen=True)
class OutAndBackController:
    forward_actions: Sequence[str] = DEFAULT_FORWARD_ACTIONS

    def actions_for_episode(
        self,
        *,
        start_pose: object,
        target_pose: object,
    ) -> tuple[str, ...]:
        del start_pose, target_pose
        forward = tuple(self.forward_actions)
        return forward + TURN_AROUND + invert_habitat_actions(forward) + TURN_AROUND
