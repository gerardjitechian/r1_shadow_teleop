import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
calibration_module = importlib.import_module(
    "r1_shadow_teleop.r1_calibration"
)

AbductionSpreadRange = calibration_module.AbductionSpreadRange
FINGERS = calibration_module.FINGERS
LoadedCalibration = calibration_module.LoadedCalibration
abduction_diagnostics = calibration_module.abduction_diagnostics
load_calibration = calibration_module.load_calibration
update_calibration_registry = calibration_module.update_calibration_registry


def flexion_ranges(open_value=0.1, closed_value=0.9):
    return {
        finger: {
            "open_raw": open_value,
            "closed_raw": closed_value,
            "zero_raw": open_value,
            "one_raw": closed_value,
        }
        for finger in FINGERS
    }


def abduction_spread(neutral=0.2, reference=0.6, fingers=None):
    return {
        finger: {
            "neutral_raw": neutral,
            "reference_raw": reference,
            "max_spread_delta": abs(reference - neutral),
        }
        for finger in (fingers or FINGERS)
    }


def abduction_quality(max_std=0.01, warnings=None, fingers=None):
    return {
        "abduction": {
            finger: {
                "neutral_std": max_std,
                "reference_std": max_std,
                "max_std": max_std,
                "warnings": list(warnings or []),
            }
            for finger in (fingers or FINGERS)
        }
    }


def write_sidecar(
    directory,
    stem,
    timestamp,
    mode="both",
    flexion=None,
    abduction=None,
    quality=None,
):
    csv_path = directory / f"{stem}.csv"
    csv_path.write_text("pose,status\nplaceholder,accepted\n")
    json_path = directory / f"{stem}.json"
    metadata = {
        "schema_version": 2,
        "input_hand": "right",
        "hand": "right",
        "mode": mode,
        "dimensions": [
            dimension for dimension, ranges in (
                ("flexion", flexion),
                ("abduction", abduction),
            ) if ranges
        ],
        "selected_fingers": list(FINGERS),
        "calibrated_fingers": {
            "flexion": list((flexion or {}).keys()),
            "abduction": list((abduction or {}).keys()),
            "pinch_validation": [],
        },
        "timestamp": timestamp,
        "csv_filename": csv_path.name,
        "source_csv": str(csv_path),
        "source_json": str(json_path),
        "status": "accepted",
        "complete": bool(flexion and abduction),
        "partial": not bool(flexion and abduction),
        "aborted": False,
        "warnings": [],
        "pose_labels": [],
        "missing_poses": [],
        "flexion_ranges": flexion or {},
        "abduction_spread": abduction or {},
        "quality": quality or {},
        "pinch_validation": {},
    }
    json_path.write_text(json.dumps(metadata, indent=2) + "\n")
    update_calibration_registry(json_path, directory, metadata)
    return csv_path, json_path


def calibration_with_abduction(spread=None, quality=None, source="explicit_file"):
    if spread is None:
        spread = {"index": AbductionSpreadRange(0.2, 0.4, 0.6)}
    return LoadedCalibration(
        abduction_spread=spread,
        complete=True,
        partial=False,
        source=source,
        resolver_mode="explicit_file",
        quality=quality if quality is not None else abduction_quality(fingers=["index"]),
    )


def test_reliable_abduction_diagnostic_reports_offset_and_spread():
    calibration = calibration_with_abduction()
    diagnostic = abduction_diagnostics({"index": 0.4}, calibration)["index"]

    assert diagnostic.status == "ok"
    assert diagnostic.neutral_raw == 0.2
    assert diagnostic.reference_raw == 0.6
    assert diagnostic.signed_offset == 0.2
    assert diagnostic.spread == 0.5


def test_missing_abduction_range_suppresses_spread():
    calibration = calibration_with_abduction(spread={}, quality={"abduction": {}})
    diagnostic = abduction_diagnostics({"index": 0.4}, calibration)["index"]

    assert diagnostic.status == "missing_range"
    assert diagnostic.spread is None


def test_missing_reference_suppresses_spread():
    calibration = calibration_with_abduction(
        spread={"index": AbductionSpreadRange(0.2, 0.4, None)},
    )
    diagnostic = abduction_diagnostics({"index": 0.4}, calibration)["index"]

    assert diagnostic.status == "missing_reference"
    assert diagnostic.spread is None


def test_small_abduction_delta_suppresses_spread():
    calibration = calibration_with_abduction(
        spread={"index": AbductionSpreadRange(0.2, 0.01, 0.21)},
    )
    diagnostic = abduction_diagnostics({"index": 0.205}, calibration)["index"]

    assert diagnostic.status == "small_delta"
    assert diagnostic.spread is None


def test_quality_warning_marks_abduction_unstable():
    calibration = calibration_with_abduction(
        quality=abduction_quality(max_std=0.09, fingers=["index"]),
    )
    diagnostic = abduction_diagnostics({"index": 0.4}, calibration)["index"]

    assert diagnostic.status == "unstable"
    assert diagnostic.spread is None


def test_unrelated_pose_warning_does_not_hide_abduction_spread():
    calibration = calibration_with_abduction(
        quality={
            "abduction": {
                "index": {
                    "neutral_std": 0.001,
                    "reference_std": 0.004,
                    "max_std": 0.004,
                    "warnings": ["held pose may be unstable: flex_pinky std=0.081"],
                }
            }
        },
    )
    diagnostic = abduction_diagnostics({"index": 0.4}, calibration)["index"]

    assert diagnostic.status == "ok"
    assert diagnostic.spread == 0.5


def test_finger_specific_abduction_warning_marks_unstable():
    calibration = calibration_with_abduction(
        quality={
            "abduction": {
                "index": {
                    "neutral_std": 0.001,
                    "reference_std": 0.004,
                    "max_std": 0.004,
                    "warnings": ["held pose may be unstable: abd_index std=0.090"],
                }
            }
        },
    )
    diagnostic = abduction_diagnostics({"index": 0.4}, calibration)["index"]

    assert diagnostic.status == "unstable"
    assert diagnostic.spread is None


def test_missing_quality_metadata_recommends_recalibration():
    calibration = calibration_with_abduction(quality={"abduction": {}})
    diagnostic = abduction_diagnostics({"index": 0.4}, calibration)["index"]

    assert diagnostic.status == "metadata_missing"
    assert diagnostic.spread is None
    assert any("recalibrate" in warning for warning in diagnostic.warnings)


def test_registry_modes_report_expected_new_record_sources(tmp_path):
    explicit_csv, explicit_json = write_sidecar(
        tmp_path,
        "explicit_full",
        "2026-05-26T14:00:00",
        flexion=flexion_ranges(),
        abduction=abduction_spread(),
        quality=abduction_quality(),
    )
    write_sidecar(
        tmp_path,
        "newer_flexion",
        "2026-05-26T15:00:00",
        mode="flexion",
        flexion=flexion_ranges(0.2, 0.8),
    )

    explicit = load_calibration(str(explicit_csv), resolver_mode="composed_latest")
    latest_complete = load_calibration(
        None,
        calibration_dir=str(tmp_path),
        resolver_mode="latest_complete",
    )
    composed = load_calibration(
        None,
        calibration_dir=str(tmp_path),
        resolver_mode="composed_latest",
    )

    assert explicit.source == "explicit_file"
    assert explicit.source_files == [explicit_json]
    assert latest_complete.source == "latest_complete_registry"
    assert latest_complete.registry_path is not None
    assert composed.source == "composed_registry"
    assert "newer_flexion.json" in composed.component_sources_summary()
    assert "explicit_full.json" in composed.component_sources_summary()
