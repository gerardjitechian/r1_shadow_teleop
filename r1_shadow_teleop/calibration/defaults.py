from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CALIBRATION_DIR = (
    PACKAGE_ROOT / "runtime_data" / "senseglove_r1" / "calibrations"
)
RUNTIME_CALIBRATION_DIR = (
    Path.home() / ".ros" / "r1_shadow_teleop" / "calibrations"
)
LEGACY_CALIBRATION_DIR = PACKAGE_ROOT / "docs" / "calibrations"
DEFAULT_RIGHT_LATEST_CSV = (
    DEFAULT_CALIBRATION_DIR / "r1_right_glove_calibration_latest.csv"
)
LEGACY_RIGHT_LATEST_CSV = (
    LEGACY_CALIBRATION_DIR / "r1_right_glove_calibration_latest.csv"
)
REGISTRY_FILENAME = "calibration_registry.json"
