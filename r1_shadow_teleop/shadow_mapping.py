from dataclasses import dataclass
from typing import Dict, List


SHADOW_JOINT_NAMES = [
    "rh_FFJ1",
    "rh_FFJ2",
    "rh_FFJ3",
    "rh_FFJ4",
    "rh_RFJ1",
    "rh_RFJ2",
    "rh_RFJ3",
    "rh_RFJ4",
    "rh_THJ1",
    "rh_THJ2",
    "rh_THJ4",
    "rh_THJ5",
]


@dataclass
class ShadowTarget:
    joint_names: List[str]
    positions: List[float]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_flexion(value: float) -> float:
    """
    Normalize incoming glove flexion-ish values to 0.0..1.0.

    This is intentionally conservative. We are only printing targets for now,
    not commanding hardware.
    """
    try:
        return clamp(float(value), 0.0, 1.0)
    except Exception:
        return 0.0


def map_r1_flexion_to_shadow_targets(flexion_by_finger: Dict[str, float]) -> ShadowTarget:
    """
    First-pass mapping from 5-finger R1 data to 3-finger Shadow Hand Lite.

    R1 thumb  -> Shadow thumb
    R1 index  -> Shadow first finger
    R1 ring   -> Shadow ring finger

    R1 middle and pinky are ignored for now.
    """

    thumb = safe_flexion(flexion_by_finger.get("thumb", 0.0))
    index = safe_flexion(flexion_by_finger.get("index", 0.0))
    ring = safe_flexion(flexion_by_finger.get("ring", 0.0))

    # Conservative example joint ranges in radians.
    # These are placeholders for dry-run printing only.
    # Before commanding hardware, replace with confirmed Shadow joint limits.
    finger_base = 1.0
    finger_mid = 1.0
    finger_distal = 1.0
    finger_abduction = 0.0

    thumb_j1 = 0.8
    thumb_j2 = 0.8
    thumb_j4 = 0.8
    thumb_j5 = 0.4

    positions = [
        index * finger_distal,      # rh_FFJ1
        index * finger_mid,         # rh_FFJ2
        index * finger_base,        # rh_FFJ3
        finger_abduction,           # rh_FFJ4

        ring * finger_distal,       # rh_RFJ1
        ring * finger_mid,          # rh_RFJ2
        ring * finger_base,         # rh_RFJ3
        finger_abduction,           # rh_RFJ4

        thumb * thumb_j1,           # rh_THJ1
        thumb * thumb_j2,           # rh_THJ2
        thumb * thumb_j4,           # rh_THJ4
        thumb * thumb_j5,           # rh_THJ5
    ]

    return ShadowTarget(
        joint_names=SHADOW_JOINT_NAMES,
        positions=positions,
    )
