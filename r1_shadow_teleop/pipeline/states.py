from dataclasses import dataclass, field
from typing import Dict, List

from trajectory_msgs.msg import JointTrajectory

from r1_shadow_teleop.calibration.models import AbductionDiagnostic
from r1_shadow_teleop.senseglove_r1.frame import R1HandFrame
from r1_shadow_teleop.shadow_hand.config import HandTeleopConfig
from r1_shadow_teleop.shadow_hand.mapping_preview import ShadowTarget


@dataclass
class RawHandState:
    frame: R1HandFrame
    input_source: str
    input_hand: str
    source_topic: str
    message_count: int
    raw_flexion: Dict[str, float]
    raw_abduction: Dict[str, float]


@dataclass
class CalibratedHandState:
    raw_state: RawHandState
    calibrated_flexion: Dict[str, float]
    abduction_diagnostics: Dict[str, AbductionDiagnostic]
    abduction_role: str = "diagnostic_display_only"


@dataclass
class MappedShadowTargetState:
    calibrated_state: CalibratedHandState
    teleop_config: HandTeleopConfig
    target: ShadowTarget
    mapping_profile: str = "hand_lite_3finger_placeholder"
    mapped_from: List[str] = field(default_factory=lambda: ["calibrated_flexion"])
    abduction_used_for_shadow_mapping: bool = False


@dataclass
class FilteredShadowTargetState:
    mapped_state: MappedShadowTargetState
    target: ShadowTarget
    filter_profile: str = "pass_through"


@dataclass
class OutgoingCommandPreview:
    filtered_state: FilteredShadowTargetState
    trajectory_msg: JointTrajectory
    packet: dict
