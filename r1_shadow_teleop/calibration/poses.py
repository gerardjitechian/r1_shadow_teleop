from r1_shadow_teleop.calibration.models import FINGERS


HAND_ALIASES = {"r": "right", "right": "right", "l": "left", "left": "left"}
MODE_ALIASES = {
    "f": "flexion",
    "flex": "flexion",
    "flexion": "flexion",
    "a": "abduction",
    "abd": "abduction",
    "abduction": "abduction",
    "b": "both",
    "both": "both",
    "p": "pinch_validation",
    "pinch": "pinch_validation",
    "pinch_validation": "pinch_validation",
    "pinch-validation": "pinch_validation",
}
FINGER_ALIASES = {
    "t": "thumb",
    "thumb": "thumb",
    "i": "index",
    "index": "index",
    "m": "middle",
    "middle": "middle",
    "r": "ring",
    "ring": "ring",
    "p": "pinky",
    "pinky": "pinky",
    "little": "pinky",
}


def parse_hand(value: str) -> str:
    key = str(value).strip().lower()
    if key in HAND_ALIASES:
        return HAND_ALIASES[key]
    raise ValueError(
        f"invalid hand {value!r}; accepted: r/right, l/left"
    )


def parse_mode(value: str) -> str:
    key = str(value).strip().lower()
    if key in MODE_ALIASES:
        return MODE_ALIASES[key]
    raise ValueError(
        f"invalid calibration mode {value!r}; accepted: "
        "f/flexion, a/abduction, b/both, p/pinch_validation"
    )


def parse_fingers(value: str):
    raw = str(value).strip().lower()
    if raw in {"", "a", "all"}:
        return list(FINGERS)

    selected = []
    for item in raw.split(","):
        key = item.strip()
        if not key:
            continue
        if key not in FINGER_ALIASES:
            raise ValueError(
                f"invalid finger {item.strip()!r}; accepted: all, "
                "t/thumb, i/index, m/middle, r/ring, p/pinky"
            )
        finger = FINGER_ALIASES[key]
        if finger not in selected:
            selected.append(finger)

    if not selected:
        raise ValueError(
            "at least one finger must be selected; accepted: all, "
            "t/thumb, i/index, m/middle, r/ring, p/pinky"
        )
    return selected


def flexion_poses(fingers):
    poses = [
        {
            "pose": "flexion_relaxed_neutral",
            "dimension": "flexion",
            "finger": "all",
            "role": "relaxed_neutral",
            "title": "Flexion relaxed neutral",
            "instructions": [
                "Target: all selected fingers plus the thumb in a relaxed neutral hand.",
                "Shape: palm open, fingers naturally extended, neither curled nor locked straight.",
                "Thumb: relaxed beside the hand, not pinching; stop if anything feels strained.",
            ],
            "optional": False,
        },
        {
            "pose": "flexion_open_reference",
            "dimension": "flexion",
            "finger": "all",
            "role": "open_reference",
            "title": "Flexion open reference",
            "instructions": [
                "Target: all selected fingers open in comfortable extension.",
                "Shape: palm open, fingers straight enough to feel open but not locked back.",
                "Thumb: relaxed/open; avoid hyperextension or forcing the glove flat.",
            ],
            "optional": False,
        },
        {
            "pose": "flexion_fist_reference",
            "dimension": "flexion",
            "finger": "all",
            "role": "closed_reference",
            "title": "Flexion fist reference",
            "instructions": [
                "Target: selected fingers curled into a comfortable closed/fist posture.",
                "Shape: close the hand naturally; do not crush the glove or force the joints.",
                "Thumb: rest naturally outside or across the fingers without pressing hard.",
            ],
            "optional": False,
        },
    ]

    for finger in fingers:
        poses.extend([
            {
                "pose": f"flexion_{finger}_open",
                "dimension": "flexion",
                "finger": finger,
                "role": "open_reference",
                "title": f"{finger.title()} flexion open validation",
                "instructions": [
                    f"Target finger: keep your {finger} open in comfortable extension.",
                    "Non-target fingers and thumb: relaxed and still as much as comfortable.",
                    "Natural coupling is okay; do not force isolation or hyperextension.",
                ],
                "optional": True,
            },
            {
                "pose": f"flexion_{finger}_closed",
                "dimension": "flexion",
                "finger": finger,
                "role": "closed_reference",
                "title": f"{finger.title()} flexion closed",
                "instructions": [
                    f"Target finger: curl your {finger} closed as far as comfortable.",
                    "Non-target fingers and thumb: relaxed; slight natural movement is okay.",
                    "Do not strain to keep other fingers open or press hard into the palm.",
                ],
                "optional": True,
            },
        ])

    return poses


def abduction_poses(fingers):
    poses = [
        {
            "pose": "abduction_neutral_together",
            "dimension": "abduction",
            "finger": "all",
            "role": "neutral",
            "title": "Abduction neutral together",
            "instructions": [
                "Target: all fingers open with minimal side-to-side spread.",
                "Shape: fingers comfortably extended and gently together, not squeezed tight.",
                "Thumb: relaxed beside the hand, not pinching or pressed into the palm.",
            ],
            "optional": False,
        },
        {
            "pose": "abduction_full_splay",
            "dimension": "abduction",
            "finger": "all",
            "role": "full_splay",
            "title": "Abduction full hand splay",
            "instructions": [
                "Target: all fingers open and spread side-to-side as far as comfortable.",
                "Shape: keep fingers comfortably extended; do not curl into a fist.",
                "Thumb: open with the hand; avoid hyperextension, forcing, or strain.",
            ],
            "optional": False,
        },
    ]

    if "thumb" in fingers:
        poses.append({
            "pose": "thumb_radial_abduction_max",
            "dimension": "abduction",
            "finger": "thumb",
            "role": "thumb_radial_max",
            "title": "Thumb radial abduction max",
            "instructions": [
                "Target finger: move the thumb away from the palm as far as comfortable.",
                "Non-target fingers: open, relaxed, and still as much as comfortable.",
                "Do not lever the thumb against the glove or force the end range.",
            ],
            "optional": True,
        })

    return poses


def pinch_validation_poses(fingers):
    poses = []
    for finger in [finger for finger in fingers if finger != "thumb"]:
        poses.append({
            "pose": f"pinch_validation_thumb_{finger}",
            "dimension": "pinch_validation",
            "finger": finger,
            "role": "validation",
            "title": f"Thumb to {finger} pinch validation",
            "instructions": [
                f"Target: comfortable thumb-to-{finger} contact or near-contact.",
                "Non-target fingers: relaxed; natural coupling is okay.",
                "Validation only: touch lightly or hover close; do not press hard.",
            ],
            "optional": True,
        })
    return poses


def selected_poses(mode: str, fingers):
    poses = []
    if mode in {"flexion", "both"}:
        poses.extend(flexion_poses(fingers))
    if mode in {"abduction", "both"}:
        poses.extend(abduction_poses(fingers))
    if mode == "pinch_validation":
        poses.extend(pinch_validation_poses(fingers))
    return poses
