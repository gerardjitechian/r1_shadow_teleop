import csv
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
calibration_module = importlib.import_module('r1_shadow_teleop.r1_calibration')

FINGERS = calibration_module.FINGERS
calibration_registry_path = calibration_module.calibration_registry_path
load_calibration = calibration_module.load_calibration
update_calibration_registry = calibration_module.update_calibration_registry


def flexion_ranges(open_value, closed_value, fingers=None):
    fingers = fingers or FINGERS
    return {
        finger: {
            "open_raw": open_value,
            "closed_raw": closed_value,
            "zero_raw": open_value,
            "one_raw": closed_value,
        }
        for finger in fingers
    }


def abduction_spread(neutral, reference, fingers=None):
    fingers = fingers or FINGERS
    return {
        finger: {
            "neutral_raw": neutral,
            "reference_raw": reference,
            "max_spread_delta": abs(reference - neutral),
        }
        for finger in fingers
    }


def write_sidecar(
    directory,
    stem,
    timestamp,
    mode,
    flexion=None,
    abduction=None,
    aborted=False,
    schema_version=2,
):
    csv_path = directory / f"{stem}.csv"
    csv_path.write_text("pose,status\nplaceholder,accepted\n")
    json_path = directory / f"{stem}.json"
    dimensions = []
    if flexion:
        dimensions.append("flexion")
    if abduction:
        dimensions.append("abduction")
    metadata = {
        "schema_version": schema_version,
        "input_hand": "right",
        "hand": "right",
        "mode": mode,
        "dimensions": dimensions,
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
        "status": "aborted" if aborted else "accepted",
        "complete": not aborted,
        "partial": False,
        "aborted": aborted,
        "warnings": [],
        "pose_labels": [],
        "missing_poses": [],
        "flexion_ranges": flexion or {},
        "abduction_spread": abduction or {},
        "pinch_validation": {},
    }
    if schema_version is None:
        metadata.pop("schema_version")
    json_path.write_text(json.dumps(metadata, indent=2) + "\n")
    update_calibration_registry(json_path, directory, metadata)
    return csv_path, json_path


def write_legacy_csv(path):
    columns = ["pose", "status"] + [f"flex_{finger}" for finger in FINGERS]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerow({
            "pose": "flexion_open_reference",
            "status": "accepted",
            **{f"flex_{finger}": "0.1" for finger in FINGERS},
        })
        writer.writerow({
            "pose": "flexion_fist_reference",
            "status": "accepted",
            **{f"flex_{finger}": "0.9" for finger in FINGERS},
        })


def test_registry_update_includes_aborted_but_resolver_skips_it(tmp_path):
    write_sidecar(
        tmp_path,
        "aborted_abduction",
        "2026-05-26T15:00:00",
        "abduction",
        abduction=abduction_spread(0.2, 0.6),
        aborted=True,
    )

    registry = json.loads(calibration_registry_path(tmp_path).read_text())
    assert registry["records"][0]["aborted"] is True

    calibration = load_calibration(
        None,
        calibration_dir=str(tmp_path),
        resolver_mode="composed_latest",
    )
    assert calibration.source == "fallback"
    assert "no selectable calibration records" in calibration.warnings[0]


def test_explicit_file_ignores_newer_registry_records(tmp_path):
    explicit_csv, _ = write_sidecar(
        tmp_path,
        "explicit_full",
        "2026-05-26T14:00:00",
        "both",
        flexion=flexion_ranges(0.1, 0.7),
        abduction=abduction_spread(0.2, 0.5),
    )
    write_sidecar(
        tmp_path,
        "newer_full",
        "2026-05-26T16:00:00",
        "both",
        flexion=flexion_ranges(0.3, 0.9),
        abduction=abduction_spread(0.4, 0.8),
    )

    calibration = load_calibration(
        str(explicit_csv),
        calibration_dir=str(tmp_path),
        resolver_mode="composed_latest",
    )
    assert calibration.source == "explicit_file"
    assert calibration.flexion_ranges["index"].zero_raw == 0.1


def test_latest_complete_rejects_dimension_partial_records(tmp_path):
    write_sidecar(
        tmp_path,
        "older_flexion",
        "2026-05-26T14:00:00",
        "flexion",
        flexion=flexion_ranges(0.1, 0.8),
    )
    write_sidecar(
        tmp_path,
        "newer_abduction",
        "2026-05-26T15:00:00",
        "abduction",
        abduction=abduction_spread(0.2, 0.6),
    )

    calibration = load_calibration(
        None,
        calibration_dir=str(tmp_path),
        resolver_mode="latest_complete",
    )
    assert calibration.source == "fallback"
    assert "no complete flexion+abduction" in calibration.warnings[0]


def test_composed_latest_combines_newer_flexion_with_older_abduction(tmp_path):
    write_sidecar(
        tmp_path,
        "older_abduction",
        "2026-05-26T14:00:00",
        "abduction",
        abduction=abduction_spread(0.2, 0.6),
    )
    write_sidecar(
        tmp_path,
        "newer_flexion",
        "2026-05-26T15:00:00",
        "flexion",
        flexion=flexion_ranges(0.1, 0.8),
    )

    calibration = load_calibration(
        None,
        calibration_dir=str(tmp_path),
        resolver_mode="composed_latest",
    )
    assert calibration.source == "composed_registry"
    assert calibration.flexion_ranges["index"].zero_raw == 0.1
    assert calibration.abduction_spread["index"].neutral_raw == 0.2
    assert "newer_flexion.json" in calibration.component_sources_summary()
    assert "older_abduction.json" in calibration.component_sources_summary()


def test_composed_latest_ignores_newer_invalid_range(tmp_path):
    write_sidecar(
        tmp_path,
        "older_flexion",
        "2026-05-26T14:00:00",
        "flexion",
        flexion=flexion_ranges(0.1, 0.8, fingers=["index"]),
    )
    invalid = {
        "index": {
            "open_raw": "not-a-number",
            "closed_raw": 0.9,
            "zero_raw": "not-a-number",
            "one_raw": 0.9,
        }
    }
    write_sidecar(
        tmp_path,
        "newer_invalid_flexion",
        "2026-05-26T15:00:00",
        "flexion",
        flexion=invalid,
    )

    calibration = load_calibration(
        None,
        calibration_dir=str(tmp_path),
        resolver_mode="composed_latest",
    )
    assert calibration.flexion_ranges["index"].zero_raw == 0.1


def test_legacy_csv_only_file_loads_by_inference(tmp_path):
    csv_path = tmp_path / "legacy.csv"
    write_legacy_csv(csv_path)

    calibration = load_calibration(str(csv_path), resolver_mode="explicit_file")
    assert calibration.source == "legacy_csv_only"
    assert calibration.has_complete_flexion()
    assert any("metadata sidecar not found" in item for item in calibration.warnings)


def test_legacy_sidecar_without_schema_version_is_parsed(tmp_path):
    csv_path, json_path = write_sidecar(
        tmp_path,
        "legacy_sidecar",
        "2026-05-26T14:00:00",
        "both",
        flexion=flexion_ranges(0.1, 0.8),
        abduction=abduction_spread(0.2, 0.6),
        schema_version=None,
    )

    calibration = load_calibration(str(csv_path), resolver_mode="explicit_file")
    assert json_path.exists()
    assert calibration.source == "explicit_file"
    assert calibration.has_complete_flexion()
    assert calibration.has_complete_abduction()
