from r1_shadow_teleop.calibration.diagnostics import (
    abduction_diagnostics,
    calibrate_flexion,
)
from r1_shadow_teleop.calibration.models import LoadedCalibration
from r1_shadow_teleop.pipeline.states import (
    CalibratedHandState,
    FilteredShadowTargetState,
    MappedShadowTargetState,
    OutgoingCommandPreview,
    RawHandState,
)
from r1_shadow_teleop.senseglove_r1.frame import R1HandFrame
from r1_shadow_teleop.shadow_hand.command_packet import trajectory_to_packet
from r1_shadow_teleop.shadow_hand.config import HandTeleopConfig
from r1_shadow_teleop.shadow_hand.mapping_preview import map_r1_flexion_to_shadow_targets
from r1_shadow_teleop.shadow_hand.trajectory import build_shadow_joint_trajectory


def raw_state_from_r1_frame(
    frame: R1HandFrame,
    teleop_config: HandTeleopConfig,
) -> RawHandState:
    return RawHandState(
        frame=frame,
        input_source=teleop_config.input_source,
        input_hand=teleop_config.input_hand,
        source_topic=frame.source_topic,
        message_count=frame.message_count,
        raw_flexion=frame.raw_flexion_by_finger(),
        raw_abduction=frame.raw_abduction_by_finger(),
    )


def calibrate_hand_state(
    raw_state: RawHandState,
    calibration: LoadedCalibration,
) -> CalibratedHandState:
    flexion_ranges = (
        calibration.flexion_ranges
        if calibration.has_complete_flexion()
        else None
    )
    return CalibratedHandState(
        raw_state=raw_state,
        calibrated_flexion=calibrate_flexion(
            raw_state.raw_flexion,
            ranges=flexion_ranges,
        ),
        abduction_diagnostics=abduction_diagnostics(
            raw_state.raw_abduction,
            calibration,
        ),
    )


def map_calibrated_state_to_shadow(
    calibrated_state: CalibratedHandState,
    teleop_config: HandTeleopConfig,
) -> MappedShadowTargetState:
    return MappedShadowTargetState(
        calibrated_state=calibrated_state,
        teleop_config=teleop_config,
        target=map_r1_flexion_to_shadow_targets(
            calibrated_state.calibrated_flexion,
        ),
    )


def pass_through_filter(
    mapped_state: MappedShadowTargetState,
) -> FilteredShadowTargetState:
    return FilteredShadowTargetState(
        mapped_state=mapped_state,
        target=mapped_state.target,
    )


def build_outgoing_command_preview(
    filtered_state: FilteredShadowTargetState,
    duration_sec: float = 2.0,
) -> OutgoingCommandPreview:
    trajectory_msg = build_shadow_joint_trajectory(
        filtered_state.target,
        duration_sec=duration_sec,
    )
    return OutgoingCommandPreview(
        filtered_state=filtered_state,
        trajectory_msg=trajectory_msg,
        packet=trajectory_to_packet(trajectory_msg),
    )


def build_dry_run_pipeline(
    frame: R1HandFrame,
    calibration: LoadedCalibration,
    teleop_config: HandTeleopConfig,
    duration_sec: float = 2.0,
) -> OutgoingCommandPreview:
    raw_state = raw_state_from_r1_frame(frame, teleop_config)
    calibrated_state = calibrate_hand_state(raw_state, calibration)
    mapped_state = map_calibrated_state_to_shadow(calibrated_state, teleop_config)
    filtered_state = pass_through_filter(mapped_state)
    return build_outgoing_command_preview(filtered_state, duration_sec=duration_sec)
