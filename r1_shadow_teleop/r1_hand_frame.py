from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


FINGER_ORDER = ["thumb", "index", "middle", "ring", "pinky"]


@dataclass
class FingerPose:
    name: str
    flexion_raw: float
    abduction_raw: float
    fingertip_position: Optional[Tuple[float, float, float]]
    fingertip_orientation: Optional[Tuple[float, float, float, float]]
    thumb_distance_mm: Optional[float]
    sensed_force_mn: Optional[float]


@dataclass
class R1HandFrame:
    source_topic: str
    message_count: int
    finger_names: List[str]
    fingers: Dict[str, FingerPose]

    def raw_flexion_by_finger(self) -> Dict[str, float]:
        return {
            finger: self.fingers[finger].flexion_raw
            for finger in FINGER_ORDER
            if finger in self.fingers
        }

    def raw_abduction_by_finger(self) -> Dict[str, float]:
        return {
            finger: self.fingers[finger].abduction_raw
            for finger in FINGER_ORDER
            if finger in self.fingers
        }


def _scaled_normalized_value(values: List[float], index: int) -> float:
    if index >= len(values):
        return 0.0
    return float(values[index]) / 10000.0


def _point_tuple(points, index: int) -> Optional[Tuple[float, float, float]]:
    if index >= len(points):
        return None
    point = points[index]
    return (float(point.x), float(point.y), float(point.z))


def _quaternion_tuple(
    orientations,
    index: int,
) -> Optional[Tuple[float, float, float, float]]:
    if index >= len(orientations):
        return None
    orientation = orientations[index]
    return (
        float(orientation.x),
        float(orientation.y),
        float(orientation.z),
        float(orientation.w),
    )


def _optional_float(values: List[float], index: int) -> Optional[float]:
    if index >= len(values):
        return None
    return float(values[index])


def parse_r1_glove_state(msg, source_topic: str, message_count: int) -> R1HandFrame:
    normalized_values = list(msg.normalized_finger_positions)
    fingertip_positions = list(msg.finger_tip_positions)
    fingertip_orientations = list(msg.finger_tip_orientations)
    finger_distances = list(msg.finger_distances)
    sensed_forces = list(msg.sensed_forces)

    fingers = {}

    for finger_index, finger_name in enumerate(FINGER_ORDER):
        distance_index = finger_index - 1
        force = _optional_float(sensed_forces, finger_index)

        fingers[finger_name] = FingerPose(
            name=finger_name,
            flexion_raw=_scaled_normalized_value(normalized_values, finger_index),
            abduction_raw=_scaled_normalized_value(
                normalized_values,
                finger_index + len(FINGER_ORDER),
            ),
            fingertip_position=_point_tuple(fingertip_positions, finger_index),
            fingertip_orientation=_quaternion_tuple(
                fingertip_orientations,
                finger_index,
            ),
            thumb_distance_mm=(
                _optional_float(finger_distances, distance_index)
                if distance_index >= 0
                else None
            ),
            sensed_force_mn=force,
        )

    return R1HandFrame(
        source_topic=source_topic,
        message_count=message_count,
        finger_names=list(msg.finger_names),
        fingers=fingers,
    )
