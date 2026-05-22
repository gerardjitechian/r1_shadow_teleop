from typing import Dict


FINGERS = ["thumb", "index", "middle", "ring", "pinky"]


# Right glove calibration from r1_right_glove_pose_calibration.csv.
# Values are scaled normalized_finger_positions values, already divided by 10000.
OPEN_FLEXION = {
    "thumb": 0.3757805565320029,
    "index": 0.1849250662409019,
    "middle": 0.16776884902526096,
    "ring": 0.1961606877464483,
    "pinky": 0.1866394426476648,
}


# Use isolated-finger poses where available.
# These are provisional and safe for dry-run printing only.
CLOSED_FLEXION = {
    "thumb": 1.0,                  # thumb_only
    "index": 0.9335116887731655,   # index_only
    "middle": 0.9181192112454251,  # middle_only
    "ring": 0.8937802764783622,    # ring_only
    "pinky": 0.7779156735673135,   # pinky_only
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def calibrate_finger(raw_value: float, finger: str) -> float:
    open_value = OPEN_FLEXION[finger]
    closed_value = CLOSED_FLEXION[finger]
    span = closed_value - open_value

    if abs(span) < 1e-6:
        return 0.0

    return clamp((float(raw_value) - open_value) / span)


def calibrate_flexion(raw_flexion_by_finger: Dict[str, float]) -> Dict[str, float]:
    return {
        finger: calibrate_finger(raw_flexion_by_finger.get(finger, 0.0), finger)
        for finger in FINGERS
    }
