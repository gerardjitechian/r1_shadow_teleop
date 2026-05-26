from dataclasses import dataclass
from typing import Dict, List


SUPPORTED_INPUT_SOURCES = ["senseglove_r1"]
SUPPORTED_HANDS = ["right", "left"]
SUPPORTED_SHADOW_HAND_MODELS = ["hand_lite_3finger", "hand_full_5finger"]
SUPPORTED_MIRROR_MODES = ["none"]


HAND_LITE_3FINGER_JOINT_NAMES = [
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

HAND_FULL_5FINGER_JOINT_NAMES = [
    "rh_FFJ1",
    "rh_FFJ2",
    "rh_FFJ3",
    "rh_FFJ4",
    "rh_MFJ1",
    "rh_MFJ2",
    "rh_MFJ3",
    "rh_MFJ4",
    "rh_RFJ1",
    "rh_RFJ2",
    "rh_RFJ3",
    "rh_RFJ4",
    "rh_LFJ1",
    "rh_LFJ2",
    "rh_LFJ3",
    "rh_LFJ4",
    "rh_LFJ5",
    "rh_THJ1",
    "rh_THJ2",
    "rh_THJ3",
    "rh_THJ4",
    "rh_THJ5",
]


@dataclass(frozen=True)
class ShadowHandModel:
    name: str
    description: str
    active_digits: List[str]
    joint_names: List[str]
    mapping_supported: bool


SHADOW_HAND_MODELS: Dict[str, ShadowHandModel] = {
    "hand_lite_3finger": ShadowHandModel(
        name="hand_lite_3finger",
        description="Right Shadow Hand Lite-style thumb/first/ring dry-run model",
        active_digits=["thumb", "first", "ring"],
        joint_names=HAND_LITE_3FINGER_JOINT_NAMES,
        mapping_supported=True,
    ),
    "hand_full_5finger": ShadowHandModel(
        name="hand_full_5finger",
        description="Future full 5-finger Shadow Hand model metadata",
        active_digits=["thumb", "first", "middle", "ring", "little"],
        joint_names=HAND_FULL_5FINGER_JOINT_NAMES,
        mapping_supported=False,
    ),
}


@dataclass(frozen=True)
class HandTeleopConfig:
    input_source: str = "senseglove_r1"
    input_hand: str = "right"
    target_hand: str = "right"
    shadow_hand_model: str = "hand_lite_3finger"
    mirror_mode: str = "none"

    @property
    def model(self) -> ShadowHandModel:
        return SHADOW_HAND_MODELS[self.shadow_hand_model]

    def summary(self) -> str:
        return (
            f"input_source={self.input_source}; "
            f"input_hand={self.input_hand}; "
            f"target_hand={self.target_hand}; "
            f"shadow_hand_model={self.shadow_hand_model}; "
            f"mirror_mode={self.mirror_mode}"
        )

    def warnings(self) -> List[str]:
        warnings = []
        if not self.model.mapping_supported:
            warnings.append(
                f"{self.shadow_hand_model} is recognized but not mapped yet; "
                "using dry-run metadata only"
            )
        return warnings


def _normalized(value: str) -> str:
    return str(value).strip().lower().replace("-", "_")


def _require_supported(name: str, value: str, supported: List[str]) -> str:
    normalized = _normalized(value)
    if normalized not in supported:
        accepted = ", ".join(supported)
        raise ValueError(f"unsupported {name} {value!r}; accepted: {accepted}")
    return normalized


def resolve_hand_teleop_config(
    input_source: str = "senseglove_r1",
    input_hand: str = "right",
    target_hand: str = "right",
    shadow_hand_model: str = "hand_lite_3finger",
    mirror_mode: str = "none",
) -> HandTeleopConfig:
    return HandTeleopConfig(
        input_source=_require_supported(
            "input_source",
            input_source,
            SUPPORTED_INPUT_SOURCES,
        ),
        input_hand=_require_supported("input_hand", input_hand, SUPPORTED_HANDS),
        target_hand=_require_supported("target_hand", target_hand, SUPPORTED_HANDS),
        shadow_hand_model=_require_supported(
            "shadow_hand_model",
            shadow_hand_model,
            SUPPORTED_SHADOW_HAND_MODELS,
        ),
        mirror_mode=_require_supported(
            "mirror_mode",
            mirror_mode,
            SUPPORTED_MIRROR_MODES,
        ),
    )
