import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

from r1_shadow_teleop.calibration.models import (
    AbductionSpreadRange,
    CalibrationRange,
)
from r1_shadow_teleop.calibration.storage import (
    canonical_calibration_metadata,
    ranges_to_metadata,
    spreads_to_metadata,
    update_calibration_registry,
)


FINGER_COLUMNS = [
    "flex_thumb",
    "flex_index",
    "flex_middle",
    "flex_ring",
    "flex_pinky",
    "abd_thumb",
    "abd_index",
    "abd_middle",
    "abd_ring",
    "abd_pinky",
]
STD_COLUMNS = [f"{name}_std" for name in FINGER_COLUMNS]
RAW_ANGLE_COLUMNS = [
    "raw_flex_angle_thumb",
    "raw_flex_angle_index",
    "raw_flex_angle_middle",
    "raw_flex_angle_ring",
    "raw_flex_angle_pinky",
    "raw_abd_angle_thumb",
    "raw_abd_angle_index",
    "raw_abd_angle_middle",
    "raw_abd_angle_ring",
    "raw_abd_angle_pinky",
]
CSV_COLUMNS = [
    "pose",
    "dimension",
    "finger",
    "role",
    "hand",
    "selected_mode",
    "selected_fingers",
    "timestamp",
    "settle_seconds",
    "sample_seconds",
    "status",
    "attempt",
    "sample_count",
    "warnings",
] + FINGER_COLUMNS + STD_COLUMNS + RAW_ANGLE_COLUMNS


def sample_warnings(pose, means, stddevs, sample_count):
    warnings = []
    if sample_count < 5:
        warnings.append(f"low sample count ({sample_count})")
    high_std = []
    for name, stddev in zip(FINGER_COLUMNS, stddevs):
        if stddev > 0.08:
            high_std.append(f"{name} std={stddev:.3f}")
    if high_std:
        warnings.append("held pose may be unstable: " + ", ".join(high_std[:3]))
    return warnings


def blank_row(config, pose, status, attempt, warnings=None):
    row = {
        "pose": pose["pose"],
        "dimension": pose["dimension"],
        "finger": pose["finger"],
        "role": pose["role"],
        "hand": config["hand"],
        "selected_mode": config["mode"],
        "selected_fingers": ",".join(config["fingers"]),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "settle_seconds": config["settle_seconds"],
        "sample_seconds": config["sample_seconds"],
        "status": status,
        "attempt": attempt,
        "sample_count": 0,
        "warnings": "; ".join(warnings or []),
    }
    for column in FINGER_COLUMNS + STD_COLUMNS + RAW_ANGLE_COLUMNS:
        row[column] = ""
    return row


def row_from_sample(config, pose, means, stddevs, sample_count, status, attempt, warnings):
    row = blank_row(config, pose, status, attempt, warnings)
    row["sample_count"] = sample_count
    for name, value in zip(FINGER_COLUMNS, means):
        row[name] = value
    for name, value in zip(STD_COLUMNS, stddevs):
        row[name] = value
    return row


def accepted_rows(rows):
    return [row for row in rows if row.get("status") == "accepted"]


def row_by_pose(rows):
    return {row["pose"]: row for row in accepted_rows(rows)}


def value(row, column):
    return float(row[column])


def compute_flexion_ranges(rows, fingers):
    rows_by_pose = row_by_pose(rows)
    ranges = {}
    open_row = rows_by_pose.get("flexion_open_reference")
    fist_row = rows_by_pose.get("flexion_fist_reference")

    if not open_row:
        return ranges

    for finger in fingers:
        open_finger_row = rows_by_pose.get(f"flexion_{finger}_open") or open_row
        closed_finger_row = rows_by_pose.get(f"flexion_{finger}_closed") or fist_row
        if not closed_finger_row:
            continue
        ranges[finger] = CalibrationRange(
            value(open_finger_row, f"flex_{finger}"),
            value(closed_finger_row, f"flex_{finger}"),
        )
    return ranges


def compute_abduction_spread(rows, fingers):
    rows_by_pose = row_by_pose(rows)
    neutral_row = rows_by_pose.get("abduction_neutral_together")
    full_splay_row = rows_by_pose.get("abduction_full_splay")
    thumb_row = rows_by_pose.get("thumb_radial_abduction_max")
    spreads = {}

    if not neutral_row or not full_splay_row:
        return spreads

    for finger in fingers:
        reference_row = thumb_row if finger == "thumb" and thumb_row else full_splay_row
        neutral = value(neutral_row, f"abd_{finger}")
        reference = value(reference_row, f"abd_{finger}")
        spreads[finger] = AbductionSpreadRange(
            neutral_raw=neutral,
            reference_raw=reference,
            max_spread_delta=abs(reference - neutral),
        )
    return spreads


def std_value(row, column):
    raw_value = row.get(column)
    if raw_value in {None, ""}:
        return None
    return float(raw_value)


def row_warning_list(finger, *rows):
    warnings = []
    needle = f"abd_{finger}"
    for row in rows:
        warning = row.get("warnings") if row else ""
        if warning and needle in warning:
            warnings.append(warning)
    return warnings


def compute_quality(rows, fingers):
    rows_by_pose = row_by_pose(rows)
    neutral_row = rows_by_pose.get("abduction_neutral_together")
    full_splay_row = rows_by_pose.get("abduction_full_splay")
    thumb_row = rows_by_pose.get("thumb_radial_abduction_max")
    quality = {"abduction": {}}

    if not neutral_row or not full_splay_row:
        return quality

    for finger in fingers:
        reference_row = thumb_row if finger == "thumb" and thumb_row else full_splay_row
        neutral_std = std_value(neutral_row, f"abd_{finger}_std")
        reference_std = std_value(reference_row, f"abd_{finger}_std")
        stddevs = [item for item in (neutral_std, reference_std) if item is not None]
        max_std = max(stddevs) if stddevs else None
        warnings = row_warning_list(finger, neutral_row, reference_row)
        if max_std is not None and max_std > 0.08:
            warnings.append(f"abd_{finger} max std={max_std:.3f}")
        quality["abduction"][finger] = {
            "neutral_std": neutral_std,
            "reference_std": reference_std,
            "max_std": max_std,
            "warnings": warnings,
        }

    return quality


def compute_pinch_validation(rows):
    validation = {}
    for row in accepted_rows(rows):
        if row.get("dimension") == "pinch_validation":
            validation[row["pose"]] = {
                column: row[column]
                for column in FINGER_COLUMNS
            }
    return validation


def final_warnings(rows, fingers, flexion_ranges, abduction_spread, mode):
    warnings = []
    skipped = [row["pose"] for row in rows if row.get("status") == "skipped"]
    if skipped:
        warnings.append("skipped poses: " + ", ".join(skipped))

    if mode in {"flexion", "both"}:
        for finger in fingers:
            if finger not in flexion_ranges:
                warnings.append(f"missing {finger} flexion range")
                continue
            rng = flexion_ranges[finger]
            if rng.zero_raw >= rng.one_raw:
                warnings.append(f"{finger} flexion open value >= closed value")
            if abs(rng.one_raw - rng.zero_raw) < 0.05:
                warnings.append(f"{finger} flexion range is very small")

    if mode in {"abduction", "both"}:
        for finger in fingers:
            if finger not in abduction_spread:
                warnings.append(f"missing {finger} abduction spread")
                continue
            spread = abduction_spread[finger]
            if spread.max_spread_delta < 0.03:
                warnings.append(f"{finger} abduction splay is close to neutral")

    for row in rows:
        if row.get("warnings"):
            warnings.append(f"{row['pose']}: {row['warnings']}")

    return warnings


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 100):
        candidate = path.with_name(f"{path.stem}_{index:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find available filename based on {path}")


def output_paths(config, suffix=""):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    default_stem = f"r1_{config['hand']}_glove_calibration_{timestamp}{suffix}"
    stem = config["output_name"] or default_stem
    if suffix and config["output_name"] and not stem.endswith(suffix):
        stem = f"{stem}{suffix}"
    if stem.endswith(".csv"):
        stem = stem[:-4]
    output_dir = config["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = unique_path(output_dir / f"{stem}.csv")
    return csv_path, csv_path.with_suffix(".json")


def latest_paths(output_dir: Path, hand: str):
    stem = f"r1_{hand}_glove_calibration_latest"
    return output_dir / f"{stem}.csv", output_dir / f"{stem}.json"


def write_outputs(config, rows, aborted=False):
    accepted_required = all(
        row.get("status") == "accepted"
        for row in rows
        if not row.get("optional_pose", False)
    )
    flexion_ranges = compute_flexion_ranges(rows, config["fingers"])
    abduction_spread = compute_abduction_spread(rows, config["fingers"])
    pinch_validation = compute_pinch_validation(rows)
    quality = compute_quality(rows, config["fingers"])
    warnings = final_warnings(rows, config["fingers"], flexion_ranges, abduction_spread, config["mode"])
    complete = bool(accepted_required and not aborted)
    if config["mode"] in {"flexion", "both"}:
        complete = complete and all(f in flexion_ranges for f in config["fingers"])
    if config["mode"] in {"abduction", "both"}:
        complete = complete and all(f in abduction_spread for f in config["fingers"])

    partial = not complete
    suffix = "_incomplete" if partial or aborted else ""
    csv_path, json_path = output_paths(config, suffix=suffix)

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    dimensions = []
    if flexion_ranges:
        dimensions.append("flexion")
    if abduction_spread:
        dimensions.append("abduction")
    if pinch_validation:
        dimensions.append("pinch_validation")

    metadata = {
        "schema_version": 2,
        "input_hand": config["hand"],
        "hand": config["hand"],
        "mode": config["mode"],
        "dimensions": dimensions,
        "selected_fingers": config["fingers"],
        "calibrated_fingers": {
            "flexion": list(flexion_ranges.keys()),
            "abduction": list(abduction_spread.keys()),
            "pinch_validation": list(pinch_validation.keys()),
        },
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "csv_filename": csv_path.name,
        "source_csv": str(csv_path),
        "source_json": str(json_path),
        "status": "aborted" if aborted else "accepted",
        "complete": complete,
        "partial": partial,
        "aborted": aborted,
        "missing_poses": [row["pose"] for row in rows if row.get("status") != "accepted"],
        "warnings": warnings,
        "pose_labels": [row["pose"] for row in rows],
        "flexion_ranges": ranges_to_metadata(flexion_ranges, ("open_raw", "closed_raw")),
        "abduction_spread": spreads_to_metadata(abduction_spread),
        "quality": quality,
        "pinch_validation": pinch_validation,
        "sdk_notes": {
            "raw_percentage_bent_angles_available": False,
            "source": "R1GloveState.normalized_finger_positions",
        },
    }
    metadata = canonical_calibration_metadata(metadata, csv_path, json_path)
    json_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    update_calibration_registry(json_path, csv_path.parent, metadata)

    latest_csv = latest_json = None
    if complete:
        latest_csv, latest_json = latest_paths(csv_path.parent, config["hand"])
        shutil.copy2(csv_path, latest_csv)
        shutil.copy2(json_path, latest_json)

    return csv_path, json_path, latest_csv, latest_json, metadata
