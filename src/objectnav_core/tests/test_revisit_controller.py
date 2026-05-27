from objectnav_core.simulation.revisit_controller import (
    OutAndBackController,
    invert_habitat_actions,
)


def test_invert_habitat_actions_retraces_turns_and_forward_motion() -> None:
    actions = ("move_forward", "turn_left", "move_forward", "turn_right")

    inverse = invert_habitat_actions(actions)

    assert inverse == ("turn_left", "move_forward", "turn_right", "move_forward")


def test_out_and_back_controller_inserts_revisit_interval() -> None:
    controller = OutAndBackController(
        forward_actions=("move_forward", "turn_left", "move_forward")
    )

    actions = controller.actions_for_episode(start_pose=(0, 0, 0), target_pose=(1, 0, 0))

    assert actions[:3] == ("move_forward", "turn_left", "move_forward")
    assert actions[3:5] == ("turn_left", "turn_left")
    assert actions[5:8] == ("move_forward", "turn_right", "move_forward")
    assert actions[-2:] == ("turn_left", "turn_left")
