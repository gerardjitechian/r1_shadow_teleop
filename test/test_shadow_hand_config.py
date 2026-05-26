from pathlib import Path

import pytest

from r1_shadow_teleop.shadow_hand.config import (
    HAND_LITE_3FINGER_JOINT_NAMES,
    resolve_hand_teleop_config,
)
from r1_shadow_teleop.shadow_hand.mapping_preview import (
    SHADOW_JOINT_NAMES,
    map_r1_flexion_to_shadow_targets,
)


def test_default_teleop_config_is_senseglove_r1_to_right_hand_lite():
    config = resolve_hand_teleop_config()

    assert config.input_source == "senseglove_r1"
    assert config.input_hand == "right"
    assert config.target_hand == "right"
    assert config.shadow_hand_model == "hand_lite_3finger"
    assert config.mirror_mode == "none"
    assert config.model.mapping_supported is True
    assert config.warnings() == []


def test_hand_full_5finger_is_known_metadata_without_mapping_support():
    config = resolve_hand_teleop_config(shadow_hand_model="hand_full_5finger")

    assert config.shadow_hand_model == "hand_full_5finger"
    assert config.model.mapping_supported is False
    assert "not mapped yet" in config.warnings()[0]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"input_source": "meta_quest"}, "unsupported input_source"),
        ({"mirror_mode": "left_to_right"}, "unsupported mirror_mode"),
        ({"input_hand": "center"}, "unsupported input_hand"),
        ({"target_hand": "center"}, "unsupported target_hand"),
        (
            {"shadow_hand_model": "unknown_hand"},
            "unsupported shadow_hand_model",
        ),
    ],
)
def test_unsupported_teleop_config_values_fail_clearly(kwargs, message):
    with pytest.raises(ValueError, match=message):
        resolve_hand_teleop_config(**kwargs)


def test_hand_lite_metadata_matches_current_mapping_joint_order():
    assert SHADOW_JOINT_NAMES == HAND_LITE_3FINGER_JOINT_NAMES


def test_default_mapping_output_remains_unchanged():
    target = map_r1_flexion_to_shadow_targets(
        {"thumb": 0.5, "index": 0.25, "ring": 0.75}
    )

    assert target.joint_names == HAND_LITE_3FINGER_JOINT_NAMES
    assert target.positions == [
        0.25,
        0.25,
        0.25,
        0.0,
        0.75,
        0.75,
        0.75,
        0.0,
        0.4,
        0.4,
        0.4,
        0.2,
    ]


def test_listener_declares_phase6_config_parameters():
    source = Path("r1_shadow_teleop/dashboard/listener_node.py").read_text()

    assert 'declare_parameter("input_source", "senseglove_r1")' in source
    assert 'declare_parameter("input_hand", "right")' in source
    assert 'declare_parameter("target_hand", "right")' in source
    assert 'declare_parameter("shadow_hand_model", "hand_lite_3finger")' in source
    assert 'declare_parameter("mirror_mode", "none")' in source
    assert "teleop_config:" in source
    assert "hand=self.teleop_config.input_hand" in source
    assert "mapping_profile:" in source
    assert "mapped_from: calibrated_flexion" in source
    assert "abduction_used_for_shadow_mapping: false" in source
    assert "filter_profile: pass_through" in source
