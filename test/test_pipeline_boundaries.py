from r1_shadow_teleop.calibration.diagnostics import (
    abduction_diagnostics,
    calibrate_flexion,
)
from r1_shadow_teleop.calibration.models import (
    FINGERS,
    AbductionSpreadRange,
    CalibrationRange,
    LoadedCalibration,
)
from r1_shadow_teleop.pipeline.flow import (
    build_dry_run_pipeline,
    build_outgoing_command_preview,
    calibrate_hand_state,
    map_calibrated_state_to_shadow,
    pass_through_filter,
    raw_state_from_r1_frame,
)
from r1_shadow_teleop.senseglove_r1.frame import FingerPose, R1HandFrame
from r1_shadow_teleop.shadow_hand.config import (
    HAND_LITE_3FINGER_JOINT_NAMES,
    resolve_hand_teleop_config,
)


def make_frame():
    fingers = {}
    for index, finger in enumerate(FINGERS):
        fingers[finger] = FingerPose(
            name=finger,
            flexion_raw=0.1 + index * 0.1,
            abduction_raw=0.2 + index * 0.05,
            fingertip_position=None,
            fingertip_orientation=None,
            thumb_distance_mm=None,
            sensed_force_mn=None,
        )
    return R1HandFrame(
        source_topic="/r1/test",
        message_count=7,
        finger_names=list(FINGERS),
        fingers=fingers,
    )


def make_calibration():
    return LoadedCalibration(
        hand="right",
        flexion_ranges={
            finger: CalibrationRange(0.0, 1.0)
            for finger in FINGERS
        },
        abduction_spread={
            finger: AbductionSpreadRange(0.2, 0.4, 0.6)
            for finger in FINGERS
        },
        quality={
            "abduction": {
                finger: {
                    "neutral_std": 0.01,
                    "reference_std": 0.01,
                    "max_std": 0.01,
                    "warnings": [],
                }
                for finger in FINGERS
            }
        },
        complete=True,
        partial=False,
        source="composed_registry",
        resolver_mode="composed_latest",
    )


def test_raw_state_wraps_r1_frame_values():
    frame = make_frame()
    config = resolve_hand_teleop_config()
    raw_state = raw_state_from_r1_frame(frame, config)

    assert raw_state.frame is frame
    assert raw_state.input_source == "senseglove_r1"
    assert raw_state.input_hand == "right"
    assert raw_state.source_topic == "/r1/test"
    assert raw_state.message_count == 7
    assert raw_state.raw_flexion == frame.raw_flexion_by_finger()
    assert raw_state.raw_abduction == frame.raw_abduction_by_finger()


def test_calibrated_state_matches_existing_calibration_helpers():
    frame = make_frame()
    config = resolve_hand_teleop_config()
    calibration = make_calibration()
    raw_state = raw_state_from_r1_frame(frame, config)
    calibrated_state = calibrate_hand_state(raw_state, calibration)

    assert calibrated_state.calibrated_flexion == calibrate_flexion(
        raw_state.raw_flexion,
        calibration.flexion_ranges,
    )
    assert calibrated_state.abduction_diagnostics == abduction_diagnostics(
        raw_state.raw_abduction,
        calibration,
    )
    assert calibrated_state.abduction_role == "diagnostic_display_only"


def test_mapped_and_filtered_states_preserve_current_placeholder_mapping():
    frame = make_frame()
    config = resolve_hand_teleop_config()
    calibration = make_calibration()
    raw_state = raw_state_from_r1_frame(frame, config)
    calibrated_state = calibrate_hand_state(raw_state, calibration)
    mapped_state = map_calibrated_state_to_shadow(calibrated_state, config)
    filtered_state = pass_through_filter(mapped_state)

    assert mapped_state.mapping_profile == "hand_lite_3finger_placeholder"
    assert mapped_state.mapped_from == ["calibrated_flexion"]
    assert mapped_state.abduction_used_for_shadow_mapping is False
    assert mapped_state.target.joint_names == HAND_LITE_3FINGER_JOINT_NAMES
    assert filtered_state.filter_profile == "pass_through"
    assert filtered_state.target is mapped_state.target


def test_outgoing_preview_keeps_packet_schema_and_trajectory_shape():
    frame = make_frame()
    config = resolve_hand_teleop_config()
    calibration = make_calibration()
    pipeline = build_dry_run_pipeline(frame, calibration, config, duration_sec=2.0)
    trajectory = pipeline.trajectory_msg
    packet = pipeline.packet

    assert trajectory.joint_names == HAND_LITE_3FINGER_JOINT_NAMES
    assert len(trajectory.points) == 1
    assert list(trajectory.points[0].positions) == pipeline.filtered_state.target.positions
    assert trajectory.points[0].time_from_start.sec == 2
    assert trajectory.points[0].time_from_start.nanosec == 0
    assert packet["type"] == "shadow_joint_trajectory_preview"
    assert packet["source"] == "r1_glove69_rh"
    assert packet["safety"] == {
        "publish_to_robot": False,
        "dry_run_only": True,
    }
    assert packet["trajectory"]["joint_names"] == HAND_LITE_3FINGER_JOINT_NAMES
    assert packet["trajectory"]["positions"] == pipeline.filtered_state.target.positions
    assert packet["trajectory"]["duration_sec"] == 2.0


def test_outgoing_preview_builder_preserves_filtered_state_reference():
    frame = make_frame()
    config = resolve_hand_teleop_config()
    calibration = make_calibration()
    raw_state = raw_state_from_r1_frame(frame, config)
    calibrated_state = calibrate_hand_state(raw_state, calibration)
    mapped_state = map_calibrated_state_to_shadow(calibrated_state, config)
    filtered_state = pass_through_filter(mapped_state)
    preview = build_outgoing_command_preview(filtered_state, duration_sec=1.5)

    assert preview.filtered_state is filtered_state
    assert preview.trajectory_msg.points[0].time_from_start.sec == 1
    assert preview.trajectory_msg.points[0].time_from_start.nanosec == 500000000
