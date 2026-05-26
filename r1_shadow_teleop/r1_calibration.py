import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
DIMENSIONS = ["flexion", "abduction", "pinch_validation"]
RESOLVER_MODES = ["explicit_file", "latest_complete", "composed_latest"]
ABDUCTION_MIN_RELIABLE_DELTA = 0.03
ABDUCTION_STDDEV_WARNING_THRESHOLD = 0.08


# Built-in right glove calibration from the original pose calibration CSV.
# Values are scaled normalized_finger_positions values, already divided by 10000.
OPEN_FLEXION = {
    "thumb": 0.3757805565320029,
    "index": 0.1849250662409019,
    "middle": 0.16776884902526096,
    "ring": 0.1961606877464483,
    "pinky": 0.1866394426476648,
}

CLOSED_FLEXION = {
    "thumb": 1.0,
    "index": 0.9335116887731655,
    "middle": 0.9181192112454251,
    "ring": 0.8937802764783622,
    "pinky": 0.7779156735673135,
}

# Display-only fallback abduction spread references. These are not used for Shadow mapping.
NEUTRAL_ABDUCTION = {
    "thumb": 0.4837600563280872,
    "index": 0.2476564074970545,
    "middle": 0.2005277700536353,
    "ring": 0.0,
    "pinky": 0.0,
}

SPREAD_ABDUCTION = {
    "thumb": 1.0,
    "index": 0.6593889865958372,
    "middle": 0.6049670236939938,
    "ring": 0.49641585835324264,
    "pinky": 0.31413596022393536,
}

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_CALIBRATION_DIR = Path(__file__).resolve().parent / "calibrations"
RUNTIME_CALIBRATION_DIR = (
    Path.home() / ".ros" / "r1_shadow_teleop" / "calibrations"
)
LEGACY_CALIBRATION_DIR = PACKAGE_ROOT / "docs" / "calibrations"

# New calibration writes default to the package-local calibration directory.
# The ROS user data and docs directories are kept as read fallbacks.
DEFAULT_CALIBRATION_DIR = PACKAGE_CALIBRATION_DIR
DEFAULT_RIGHT_LATEST_CSV = (
    DEFAULT_CALIBRATION_DIR / "r1_right_glove_calibration_latest.csv"
)
LEGACY_RIGHT_LATEST_CSV = (
    LEGACY_CALIBRATION_DIR / "r1_right_glove_calibration_latest.csv"
)
REGISTRY_FILENAME = "calibration_registry.json"


@dataclass
class CalibrationRange:
    zero_raw: float
    one_raw: float

    def normalize(self, value: float) -> float:
        span = self.one_raw - self.zero_raw
        if abs(span) < 1e-6:
            return 0.0
        return clamp((float(value) - self.zero_raw) / span)


@dataclass
class AbductionSpreadRange:
    neutral_raw: float
    max_spread_delta: float
    reference_raw: Optional[float] = None

    def signed_offset(self, value: float) -> float:
        return float(value) - self.neutral_raw

    def normalize(self, value: float) -> float:
        if abs(self.max_spread_delta) < 1e-6:
            return 0.0
        return clamp(abs(self.signed_offset(value)) / abs(self.max_spread_delta))


@dataclass
class LoadedCalibration:
    csv_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    hand: str = "right"
    mode: str = "fallback"
    timestamp: str = "unknown"
    dimensions: List[str] = field(default_factory=list)
    flexion_ranges: Dict[str, CalibrationRange] = field(default_factory=dict)
    abduction_spread: Dict[str, AbductionSpreadRange] = field(default_factory=dict)
    pinch_validation: Dict[str, dict] = field(default_factory=dict)
    complete: bool = False
    partial: bool = False
    aborted: bool = False
    warnings: List[str] = field(default_factory=list)
    source: str = "fallback"
    resolver_mode: str = "fallback"
    source_files: List[Path] = field(default_factory=list)
    component_sources: Dict[str, Dict[str, str]] = field(default_factory=dict)
    quality: Dict[str, Dict[str, dict]] = field(default_factory=dict)
    registry_path: Optional[Path] = None
    selection_summary: str = ""

    def flexion_fingers(self) -> List[str]:
        return [finger for finger in FINGERS if finger in self.flexion_ranges]

    def abduction_fingers(self) -> List[str]:
        return [finger for finger in FINGERS if finger in self.abduction_spread]

    def has_complete_flexion(self) -> bool:
        return all(finger in self.flexion_ranges for finger in FINGERS)

    def has_complete_abduction(self) -> bool:
        return all(finger in self.abduction_spread for finger in FINGERS)

    def has_any_file_data(self) -> bool:
        return bool(self.flexion_ranges or self.abduction_spread or self.pinch_validation)

    def is_latest_path(self) -> bool:
        return bool(self.csv_path and self.csv_path.name.endswith("_latest.csv"))

    def contents_summary(self) -> str:
        flex = ",".join(self.flexion_fingers()) or "none"
        abd = ",".join(self.abduction_fingers()) or "none"
        parts = [f"flexion={flex}", f"abduction={abd}"]
        if self.pinch_validation:
            parts.append("pinch_validation=present")
        return "; ".join(parts)

    def status_summary(self) -> str:
        if self.source == "fallback":
            if self.warnings:
                return "fallback - " + self.warnings[0]
            return "fallback - using built-in display ranges"
        if self.aborted:
            return "incomplete - aborted"
        if self.complete and not self.partial:
            return "complete"
        if not self.flexion_ranges and self.abduction_spread:
            return "partial - abduction only"
        if self.flexion_ranges and not self.abduction_spread:
            return "partial - flexion only"
        missing = []
        for dimension, ranges in (
            ("flexion", self.flexion_ranges),
            ("abduction", self.abduction_spread),
        ):
            for finger in FINGERS:
                if finger not in ranges:
                    missing.append(f"{finger} {dimension}")
        if missing:
            return "partial - missing " + ", ".join(missing[:3]) + (
                "..." if len(missing) > 3 else ""
            )
        return "partial"

    def source_files_summary(self) -> str:
        if not self.source_files:
            return "none"
        names = []
        for path in self.source_files:
            name = Path(path).name
            if name not in names:
                names.append(name)
        return ", ".join(names)

    def component_sources_summary(self) -> str:
        if not self.component_sources:
            return "none"
        parts = []
        for dimension in ("flexion", "abduction", "pinch_validation"):
            sources = self.component_sources.get(dimension, {})
            if not sources:
                continue
            names = []
            for source in sources.values():
                name = Path(source).name
                if name not in names:
                    names.append(name)
            parts.append(f"{dimension}: {','.join(names)}")
        return "; ".join(parts) or "none"

    def uses_schema_v2_metadata(self) -> bool:
        return self.source in {
            "explicit_file",
            "latest_complete_registry",
            "composed_registry",
        }

    def is_degraded(self) -> bool:
        return (
            self.source == "fallback"
            or self.aborted
            or self.partial
            or bool(self.warnings)
            or not self.uses_schema_v2_metadata()
        )

    def diagnostic_status(self) -> str:
        if self.is_degraded():
            return "degraded"
        if self.complete:
            return "complete"
        return "partial"


@dataclass
class AbductionDiagnostic:
    finger: str
    raw_sdk: Optional[float]
    neutral_raw: Optional[float] = None
    reference_raw: Optional[float] = None
    signed_offset: Optional[float] = None
    spread: Optional[float] = None
    status: str = "unavailable"
    warnings: List[str] = field(default_factory=list)

    @property
    def reliable(self) -> bool:
        return self.status == "ok"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def built_in_flexion_ranges() -> Dict[str, CalibrationRange]:
    return {
        finger: CalibrationRange(OPEN_FLEXION[finger], CLOSED_FLEXION[finger])
        for finger in FINGERS
    }


def built_in_abduction_spread() -> Dict[str, AbductionSpreadRange]:
    return {
        finger: AbductionSpreadRange(
            neutral_raw=NEUTRAL_ABDUCTION[finger],
            reference_raw=SPREAD_ABDUCTION[finger],
            max_spread_delta=abs(SPREAD_ABDUCTION[finger] - NEUTRAL_ABDUCTION[finger]),
        )
        for finger in FINGERS
    }


def calibrate_finger(raw_value: float, finger: str) -> float:
    return built_in_flexion_ranges()[finger].normalize(raw_value)


def calibrate_flexion(
    raw_flexion_by_finger: Dict[str, float],
    ranges: Optional[Dict[str, CalibrationRange]] = None,
) -> Dict[str, float]:
    active_ranges = ranges if ranges and all(f in ranges for f in FINGERS) else built_in_flexion_ranges()
    return {
        finger: active_ranges[finger].normalize(raw_flexion_by_finger.get(finger, 0.0))
        for finger in FINGERS
    }


def calibrate_abduction(
    raw_abduction_by_finger: Dict[str, float],
    spreads: Optional[Dict[str, AbductionSpreadRange]] = None,
) -> Dict[str, float]:
    active_spreads = spreads or built_in_abduction_spread()
    fallback_spreads = built_in_abduction_spread()
    return {
        finger: active_spreads.get(finger, fallback_spreads[finger]).normalize(
            raw_abduction_by_finger.get(finger, 0.0)
        )
        for finger in FINGERS
    }


def abduction_signed_offsets(
    raw_abduction_by_finger: Dict[str, float],
    spreads: Optional[Dict[str, AbductionSpreadRange]] = None,
) -> Dict[str, float]:
    active_spreads = spreads or built_in_abduction_spread()
    fallback_spreads = built_in_abduction_spread()
    return {
        finger: active_spreads.get(finger, fallback_spreads[finger]).signed_offset(
            raw_abduction_by_finger.get(finger, 0.0)
        )
        for finger in FINGERS
    }


def _warning_mentions_abduction_finger(warning: str, finger: str) -> bool:
    lowered = str(warning).lower()
    return (
        f"abd_{finger}" in lowered
        or f"abduction {finger}" in lowered
        or f"{finger} abduction" in lowered
    )


def _finger_quality_warnings(quality: dict, finger: str) -> List[str]:
    warnings = [
        warning for warning in quality.get("warnings", [])
        if _warning_mentions_abduction_finger(str(warning), finger)
    ]
    max_std = quality.get("max_std")
    try:
        if max_std is not None and float(max_std) > ABDUCTION_STDDEV_WARNING_THRESHOLD:
            warnings.append(f"abd_{finger} max_std={float(max_std):.3f}")
    except (TypeError, ValueError):
        warnings.append(f"abd_{finger} invalid quality max_std")
    return warnings


def abduction_diagnostics(
    raw_abduction_by_finger: Dict[str, float],
    calibration: LoadedCalibration,
) -> Dict[str, AbductionDiagnostic]:
    diagnostics = {}
    quality_by_finger = calibration.quality.get("abduction", {})

    for finger in FINGERS:
        if finger not in raw_abduction_by_finger:
            diagnostics[finger] = AbductionDiagnostic(finger, None)
            continue

        raw_value = float(raw_abduction_by_finger[finger])
        spread = calibration.abduction_spread.get(finger)
        if spread is None:
            diagnostics[finger] = AbductionDiagnostic(
                finger,
                raw_value,
                status="missing_range",
                warnings=["no abduction calibration range for this finger"],
            )
            continue

        diagnostic = AbductionDiagnostic(
            finger=finger,
            raw_sdk=raw_value,
            neutral_raw=spread.neutral_raw,
            reference_raw=spread.reference_raw,
            signed_offset=spread.signed_offset(raw_value),
            spread=spread.normalize(raw_value),
            status="ok",
        )

        if not calibration.uses_schema_v2_metadata():
            diagnostic.status = "metadata_missing"
            diagnostic.warnings.append("schema v2 metadata unavailable; recalibrate")
        elif finger not in quality_by_finger:
            diagnostic.status = "metadata_missing"
            diagnostic.warnings.append("quality metadata unavailable; recalibrate")
        elif diagnostic.neutral_raw is None:
            diagnostic.status = "missing_neutral"
            diagnostic.warnings.append("neutral baseline unavailable")
        elif diagnostic.reference_raw is None:
            diagnostic.status = "missing_reference"
            diagnostic.warnings.append("reference abduction unavailable")
        elif abs(spread.max_spread_delta) < ABDUCTION_MIN_RELIABLE_DELTA:
            diagnostic.status = "small_delta"
            diagnostic.warnings.append("neutral-to-reference delta is too small")
        else:
            quality_warnings = _finger_quality_warnings(quality_by_finger[finger], finger)
            if quality_warnings:
                diagnostic.status = "unstable"
                diagnostic.warnings.extend(quality_warnings)

        if not diagnostic.reliable:
            diagnostic.spread = None
        diagnostics[finger] = diagnostic

    return diagnostics


def calibrate_abduction_finger(raw_value: float, finger: str) -> float:
    return built_in_abduction_spread()[finger].normalize(raw_value)


def matching_metadata_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(".json")


def calibration_registry_path(calibration_dir: Optional[Path] = None) -> Path:
    directory = calibration_dir or DEFAULT_CALIBRATION_DIR
    return Path(directory).expanduser() / REGISTRY_FILENAME


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return datetime.min


def _sorted_metadata_items(items: List[Tuple[Path, dict]]) -> List[Tuple[Path, dict]]:
    return sorted(
        items,
        key=lambda item: _parse_timestamp(item[1].get("timestamp", "")),
        reverse=True,
    )


def _safe_record_id(metadata: dict, csv_path: Path) -> str:
    if metadata.get("record_id"):
        return str(metadata["record_id"])
    hand = str(metadata.get("input_hand") or metadata.get("hand") or "right")
    timestamp = str(metadata.get("timestamp") or csv_path.stem)
    mode = str(metadata.get("mode") or "unknown")
    safe_timestamp = "".join(
        char if char.isalnum() else "_" for char in timestamp
    ).strip("_")
    return f"r1_{hand}_{safe_timestamp}_{mode}_{csv_path.stem}"


def _status_from_metadata(metadata: dict) -> str:
    if metadata.get("status"):
        return str(metadata["status"])
    if bool(metadata.get("aborted", False)):
        return "aborted"
    if metadata.get("flexion_ranges") or metadata.get("abduction_spread"):
        return "accepted"
    return "invalid"


def _calibrated_fingers_from_metadata(metadata: dict) -> Dict[str, List[str]]:
    raw = metadata.get("calibrated_fingers")
    if isinstance(raw, dict):
        return {
            "flexion": list(raw.get("flexion", [])),
            "abduction": list(raw.get("abduction", [])),
            "pinch_validation": list(raw.get("pinch_validation", [])),
        }
    return {
        "flexion": [
            finger for finger in FINGERS
            if finger in metadata.get("flexion_ranges", {})
        ],
        "abduction": [
            finger for finger in FINGERS
            if finger in metadata.get("abduction_spread", {})
        ],
        "pinch_validation": list(metadata.get("pinch_validation", {}).keys()),
    }


def _completion_from_metadata(metadata: dict) -> dict:
    calibrated = _calibrated_fingers_from_metadata(metadata)
    return {
        "selected_scope_complete": bool(metadata.get("complete", False)),
        "flexion": calibrated["flexion"],
        "abduction": calibrated["abduction"],
        "pinch_validation": calibrated["pinch_validation"],
    }


def _metadata_source_csv(metadata: dict, json_path: Path) -> Path:
    raw_source = metadata.get("source_csv") or metadata.get("csv_filename")
    if raw_source:
        source_path = Path(str(raw_source)).expanduser()
        if source_path.is_absolute():
            return source_path
        return json_path.parent / source_path
    return json_path.with_suffix(".csv")


def _metadata_source_json(metadata: dict, json_path: Path) -> Path:
    raw_source = metadata.get("source_json")
    if raw_source:
        source_path = Path(str(raw_source)).expanduser()
        if source_path.is_absolute():
            return source_path
        return json_path.parent / source_path
    return json_path


def _relative_or_absolute(path: Path, base_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(base_dir.resolve()))
    except ValueError:
        return str(path)


def calibration_records_for_metadata(
    metadata: dict,
    csv_path: Path,
    json_path: Path,
) -> List[dict]:
    if isinstance(metadata.get("calibration_records"), list):
        return list(metadata["calibration_records"])

    records = []
    input_hand = str(metadata.get("input_hand") or metadata.get("hand") or "right")
    timestamp = str(metadata.get("timestamp", "unknown"))
    status = _status_from_metadata(metadata)
    warnings = list(metadata.get("warnings", []))
    source_csv = csv_path.name
    source_json = json_path.name

    for finger, data in metadata.get("flexion_ranges", {}).items():
        records.append({
            "input_hand": input_hand,
            "dimension": "flexion",
            "finger": finger,
            "pose_roles": ["open_reference", "closed_reference"],
            "range_kind": "open_to_closed",
            "status": status,
            "valid": _range_from_mapping(data) is not None,
            "timestamp": timestamp,
            "source_csv": source_csv,
            "source_json": source_json,
            "warnings": warnings,
        })

    for finger, data in metadata.get("abduction_spread", {}).items():
        records.append({
            "input_hand": input_hand,
            "dimension": "abduction",
            "finger": finger,
            "pose_roles": ["neutral", "full_splay"],
            "range_kind": "neutral_to_spread",
            "status": status,
            "valid": _spread_from_mapping(data) is not None,
            "timestamp": timestamp,
            "source_csv": source_csv,
            "source_json": source_json,
            "warnings": warnings,
        })

    return records


def canonical_calibration_metadata(
    metadata: dict,
    csv_path: Path,
    json_path: Path,
) -> dict:
    canonical = dict(metadata)
    canonical["schema_version"] = int(canonical.get("schema_version", 2))
    canonical["input_hand"] = str(
        canonical.get("input_hand") or canonical.get("hand") or "right"
    )
    canonical["hand"] = str(canonical.get("hand") or canonical["input_hand"])
    canonical["mode"] = str(canonical.get("mode", "unknown"))
    canonical["timestamp"] = str(canonical.get("timestamp", "unknown"))
    canonical["source_csv"] = str(csv_path)
    canonical["source_json"] = str(json_path)
    canonical["record_id"] = _safe_record_id(canonical, csv_path)
    canonical["status"] = _status_from_metadata(canonical)
    canonical["calibrated_fingers"] = _calibrated_fingers_from_metadata(canonical)
    canonical["completion"] = _completion_from_metadata(canonical)
    canonical["calibration_records"] = calibration_records_for_metadata(
        canonical,
        csv_path,
        json_path,
    )
    return canonical


def _load_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def metadata_from_sidecar(json_path: Path) -> Optional[dict]:
    metadata = _load_json(json_path)
    if metadata is None:
        return None
    csv_path = _metadata_source_csv(metadata, json_path)
    source_json = _metadata_source_json(metadata, json_path)
    return canonical_calibration_metadata(metadata, csv_path, source_json)


def registry_record_from_metadata(
    metadata: dict,
    calibration_dir: Path,
) -> dict:
    source_csv = Path(str(metadata.get("source_csv", ""))).expanduser()
    source_json = Path(str(metadata.get("source_json", ""))).expanduser()
    return {
        "record_id": metadata["record_id"],
        "input_hand": metadata["input_hand"],
        "mode": metadata.get("mode", "unknown"),
        "dimensions": list(metadata.get("dimensions", [])),
        "calibrated_fingers": _calibrated_fingers_from_metadata(metadata),
        "timestamp": metadata.get("timestamp", "unknown"),
        "source_csv": _relative_or_absolute(source_csv, calibration_dir),
        "source_json": _relative_or_absolute(source_json, calibration_dir),
        "status": metadata.get("status", "accepted"),
        "complete": bool(metadata.get("complete", False)),
        "partial": bool(metadata.get("partial", False)),
        "aborted": bool(metadata.get("aborted", False)),
        "warnings": list(metadata.get("warnings", [])),
    }


def _resolve_registry_path(value: str, registry_dir: Path) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return registry_dir / path


def read_calibration_registry(calibration_dir: Optional[Path] = None) -> dict:
    directory = Path(calibration_dir or DEFAULT_CALIBRATION_DIR).expanduser()
    path = calibration_registry_path(directory)
    data = _load_json(path)
    if not isinstance(data, dict):
        return {
            "schema_version": 1,
            "updated_at": "unknown",
            "calibration_dir": str(directory),
            "records": [],
        }
    data.setdefault("schema_version", 1)
    data.setdefault("updated_at", "unknown")
    data.setdefault("calibration_dir", str(directory))
    data.setdefault("records", [])
    return data


def write_calibration_registry(
    registry: dict,
    calibration_dir: Optional[Path] = None,
) -> Path:
    directory = Path(calibration_dir or DEFAULT_CALIBRATION_DIR).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = calibration_registry_path(directory)
    registry["schema_version"] = 1
    registry["updated_at"] = datetime.now().isoformat(timespec="seconds")
    registry["calibration_dir"] = str(directory)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    tmp_path.replace(path)
    return path


def update_calibration_registry(
    json_path: Path,
    calibration_dir: Optional[Path] = None,
    metadata: Optional[dict] = None,
) -> Path:
    directory = Path(calibration_dir or json_path.parent).expanduser()
    raw_metadata = dict(metadata) if metadata is not None else _load_json(json_path)
    if raw_metadata is None:
        raise ValueError(f"could not read calibration sidecar: {json_path}")
    csv_path = _metadata_source_csv(raw_metadata, json_path)
    canonical = canonical_calibration_metadata(raw_metadata, csv_path, json_path)
    registry = read_calibration_registry(directory)
    record = registry_record_from_metadata(canonical, directory)
    records = [
        item for item in registry.get("records", [])
        if item.get("record_id") != record["record_id"]
    ]
    records.append(record)
    registry["records"] = sorted(
        records,
        key=lambda item: _parse_timestamp(item.get("timestamp", "")),
        reverse=True,
    )
    return write_calibration_registry(registry, directory)


def _scan_sidecars(directory: Path) -> List[Path]:
    if not directory.exists():
        return []
    return sorted(
        path for path in directory.glob("*.json")
        if path.name != REGISTRY_FILENAME
    )


def candidate_sidecar_paths(
    calibration_dir: Optional[Path] = None,
) -> Tuple[List[Path], Path, List[str]]:
    directory = Path(calibration_dir or DEFAULT_CALIBRATION_DIR).expanduser()
    registry_path = calibration_registry_path(directory)
    warnings = []
    sidecars = []
    registry = _load_json(registry_path)

    if isinstance(registry, dict):
        for record in registry.get("records", []):
            source_json = record.get("source_json")
            if not source_json:
                continue
            json_path = _resolve_registry_path(str(source_json), directory)
            if json_path.exists():
                sidecars.append(json_path)
            else:
                warnings.append(f"registry record missing sidecar: {json_path}")
    else:
        sidecars = _scan_sidecars(directory)

    if not sidecars:
        sidecars = _scan_sidecars(directory)
    if not sidecars and directory != RUNTIME_CALIBRATION_DIR:
        sidecars = _scan_sidecars(RUNTIME_CALIBRATION_DIR)
        if sidecars:
            warnings.append(
                f"no package calibration records found; using ROS user data "
                f"sidecars in {RUNTIME_CALIBRATION_DIR}"
            )
    if not sidecars and directory != LEGACY_CALIBRATION_DIR:
        sidecars = _scan_sidecars(LEGACY_CALIBRATION_DIR)
        if sidecars:
            warnings.append(
                f"no package/runtime registry records found; using legacy "
                f"sidecars in {LEGACY_CALIBRATION_DIR}"
            )

    unique = []
    seen = set()
    for sidecar in sidecars:
        key = str(sidecar.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(sidecar)
    return unique, registry_path, warnings


def latest_calibration_path(
    hand: str = "right",
    calibration_dir: Optional[Path] = None,
) -> Path:
    directory = calibration_dir or DEFAULT_CALIBRATION_DIR
    return (
        Path(directory).expanduser()
        / f"r1_{hand}_glove_calibration_latest.csv"
    )


def legacy_latest_calibration_path(hand: str = "right") -> Path:
    return LEGACY_CALIBRATION_DIR / f"r1_{hand}_glove_calibration_latest.csv"


def default_calibration_path_with_legacy_fallback(
    hand: str = "right",
    calibration_dir: Optional[Path] = None,
) -> Tuple[Path, Optional[str]]:
    runtime_path = latest_calibration_path(hand, calibration_dir)
    if runtime_path.exists():
        return runtime_path, None

    ros_user_path = RUNTIME_CALIBRATION_DIR / f"r1_{hand}_glove_calibration_latest.csv"
    if ros_user_path.exists():
        warning = (
            f"default calibration not found: {runtime_path}; "
            f"using ROS user data calibration: {ros_user_path}"
        )
        return ros_user_path, warning

    legacy_path = legacy_latest_calibration_path(hand)
    if legacy_path.exists():
        warning = (
            f"default calibration not found: {runtime_path}; "
            f"using legacy calibration: {legacy_path}"
        )
        return legacy_path, warning

    return runtime_path, None


def _range_from_mapping(data: dict) -> Optional[CalibrationRange]:
    try:
        if "zero_raw" in data and "one_raw" in data:
            return CalibrationRange(float(data["zero_raw"]), float(data["one_raw"]))
        if "open_raw" in data and "closed_raw" in data:
            return CalibrationRange(float(data["open_raw"]), float(data["closed_raw"]))
    except (TypeError, ValueError):
        return None
    return None


def _spread_from_mapping(data: dict) -> Optional[AbductionSpreadRange]:
    try:
        if "neutral_raw" in data and "max_spread_delta" in data:
            return AbductionSpreadRange(
                neutral_raw=float(data["neutral_raw"]),
                reference_raw=(
                    float(data["reference_raw"])
                    if data.get("reference_raw") is not None
                    else None
                ),
                max_spread_delta=abs(float(data["max_spread_delta"])),
            )
        if "together_raw" in data and "spread_raw" in data:
            neutral = float(data["together_raw"])
            spread = float(data["spread_raw"])
            return AbductionSpreadRange(neutral, abs(spread - neutral), spread)
        if "zero_raw" in data and "one_raw" in data:
            neutral = float(data["zero_raw"])
            spread = float(data["one_raw"])
            return AbductionSpreadRange(neutral, abs(spread - neutral), spread)
    except (TypeError, ValueError):
        return None
    return None


def _ranges_from_metadata(raw_ranges: dict) -> Dict[str, CalibrationRange]:
    ranges = {}
    for finger, data in raw_ranges.items():
        if finger not in FINGERS or not isinstance(data, dict):
            continue
        calibration_range = _range_from_mapping(data)
        if calibration_range is not None:
            ranges[finger] = calibration_range
    return ranges


def _spreads_from_metadata(raw_spreads: dict) -> Dict[str, AbductionSpreadRange]:
    spreads = {}
    for finger, data in raw_spreads.items():
        if finger not in FINGERS or not isinstance(data, dict):
            continue
        spread_range = _spread_from_mapping(data)
        if spread_range is not None:
            spreads[finger] = spread_range
    return spreads


def fallback_calibration(path: Optional[Path] = None, warning: Optional[str] = None) -> LoadedCalibration:
    warnings = [warning] if warning else []
    return LoadedCalibration(
        csv_path=path,
        metadata_path=matching_metadata_path(path) if path else None,
        flexion_ranges=built_in_flexion_ranges(),
        abduction_spread=built_in_abduction_spread(),
        complete=False,
        partial=True,
        warnings=warnings,
        source="fallback",
    )


def _calibration_from_metadata(
    csv_path: Path,
    metadata_path: Path,
    metadata: dict,
    source: str,
    resolver_mode: str,
    registry_path: Optional[Path] = None,
    selection_summary: str = "",
    source_files: Optional[List[Path]] = None,
    component_sources: Optional[Dict[str, Dict[str, str]]] = None,
) -> LoadedCalibration:
    abduction_spread = _spreads_from_metadata(metadata.get("abduction_spread", {}))
    if not abduction_spread:
        abduction_spread = _spreads_from_metadata(metadata.get("abduction_ranges", {}))

    calibration = LoadedCalibration(
        csv_path=csv_path,
        metadata_path=metadata_path,
        hand=str(metadata.get("input_hand") or metadata.get("hand", "unknown")),
        mode=str(metadata.get("mode", "unknown")),
        timestamp=str(metadata.get("timestamp", "unknown")),
        dimensions=list(metadata.get("dimensions", [])),
        flexion_ranges=_ranges_from_metadata(metadata.get("flexion_ranges", {})),
        abduction_spread=abduction_spread,
        pinch_validation=dict(metadata.get("pinch_validation", {})),
        complete=bool(metadata.get("complete", False)),
        partial=bool(metadata.get("partial", False)),
        aborted=bool(metadata.get("aborted", False)),
        warnings=list(metadata.get("warnings", [])),
        source=source,
        resolver_mode=resolver_mode,
        source_files=source_files or [metadata_path],
        component_sources=component_sources or {},
        quality=dict(metadata.get("quality", {})),
        registry_path=registry_path,
        selection_summary=selection_summary,
    )

    if not calibration.component_sources:
        metadata_name = str(metadata_path)
        calibration.component_sources = {
            "flexion": {
                finger: metadata_name for finger in calibration.flexion_ranges
            },
            "abduction": {
                finger: metadata_name for finger in calibration.abduction_spread
            },
        }

    return calibration


def _load_explicit_calibration(
    csv_path: Path,
    resolver_mode: str,
    fallback_warning: Optional[str] = None,
) -> LoadedCalibration:
    metadata_path = matching_metadata_path(csv_path)

    if not csv_path.exists():
        calibration = fallback_calibration(
            csv_path,
            f"calibration file not found: {csv_path}",
        )
        calibration.resolver_mode = resolver_mode
        return calibration

    if not metadata_path.exists():
        inferred = infer_calibration_from_csv(csv_path)
        inferred.source = "legacy_csv_only"
        inferred.resolver_mode = resolver_mode
        inferred.source_files = [csv_path]
        inferred.selection_summary = "explicit legacy CSV-only calibration"
        if fallback_warning:
            inferred.warnings.append(fallback_warning)
        inferred.warnings.append(f"metadata sidecar not found: {metadata_path}")
        return inferred

    metadata = metadata_from_sidecar(metadata_path)
    if metadata is None:
        calibration = fallback_calibration(
            csv_path,
            f"could not read metadata: {metadata_path}",
        )
        calibration.resolver_mode = resolver_mode
        return calibration

    calibration = _calibration_from_metadata(
        csv_path=_metadata_source_csv(metadata, metadata_path),
        metadata_path=metadata_path,
        metadata=metadata,
        source="explicit_file",
        resolver_mode=resolver_mode,
        selection_summary="explicit calibration file",
    )
    if fallback_warning:
        calibration.warnings.append(fallback_warning)
    if not calibration.has_any_file_data():
        return fallback_calibration(csv_path, "metadata contained no usable ranges")
    return calibration


def _candidate_metadata_items(
    calibration_dir: Optional[Path],
) -> Tuple[List[Tuple[Path, dict]], Path, List[str]]:
    sidecars, registry_path, warnings = candidate_sidecar_paths(calibration_dir)
    items = []
    for json_path in sidecars:
        metadata = metadata_from_sidecar(json_path)
        if metadata is not None:
            items.append((json_path, metadata))
        else:
            warnings.append(f"could not read calibration sidecar: {json_path}")
    return _sorted_metadata_items(items), registry_path, warnings


def _is_selectable_metadata(metadata: dict, hand: str) -> bool:
    if str(metadata.get("input_hand") or metadata.get("hand")) != hand:
        return False
    if bool(metadata.get("aborted", False)):
        return False
    return metadata.get("status", "accepted") == "accepted"


def _resolve_latest_complete(
    hand: str,
    calibration_dir: Optional[Path],
) -> LoadedCalibration:
    items, registry_path, warnings = _candidate_metadata_items(calibration_dir)
    for json_path, metadata in items:
        if not _is_selectable_metadata(metadata, hand):
            continue
        csv_path = _metadata_source_csv(metadata, json_path)
        calibration = _calibration_from_metadata(
            csv_path=csv_path,
            metadata_path=json_path,
            metadata=metadata,
            source="latest_complete_registry",
            resolver_mode="latest_complete",
            registry_path=registry_path,
            selection_summary="latest complete registry calibration",
        )
        if calibration.has_complete_flexion() and calibration.has_complete_abduction():
            calibration.complete = True
            calibration.partial = False
            calibration.warnings.extend(warnings)
            return calibration

    calibration = fallback_calibration(
        latest_calibration_path(hand, calibration_dir),
        "no complete flexion+abduction calibration found in registry",
    )
    calibration.resolver_mode = "latest_complete"
    calibration.registry_path = registry_path
    calibration.selection_summary = "no registry complete calibration found"
    calibration.warnings.extend(warnings)
    return calibration


def _resolve_composed_latest(
    hand: str,
    calibration_dir: Optional[Path],
) -> LoadedCalibration:
    items, registry_path, warnings = _candidate_metadata_items(calibration_dir)
    flexion_ranges = {}
    abduction_spread = {}
    pinch_validation = {}
    quality = {"flexion": {}, "abduction": {}, "pinch_validation": {}}
    component_sources = {"flexion": {}, "abduction": {}, "pinch_validation": {}}
    source_files = []
    timestamps = []

    for json_path, metadata in items:
        if not _is_selectable_metadata(metadata, hand):
            continue
        ranges = _ranges_from_metadata(metadata.get("flexion_ranges", {}))
        spreads = _spreads_from_metadata(metadata.get("abduction_spread", {}))
        metadata_quality = metadata.get("quality", {})

        for finger, calibration_range in ranges.items():
            if finger not in flexion_ranges:
                flexion_ranges[finger] = calibration_range
                component_sources["flexion"][finger] = str(json_path)
                if finger in metadata_quality.get("flexion", {}):
                    quality["flexion"][finger] = metadata_quality["flexion"][finger]
                if json_path not in source_files:
                    source_files.append(json_path)
                timestamps.append(str(metadata.get("timestamp", "")))

        for finger, spread in spreads.items():
            if finger not in abduction_spread:
                abduction_spread[finger] = spread
                component_sources["abduction"][finger] = str(json_path)
                if finger in metadata_quality.get("abduction", {}):
                    quality["abduction"][finger] = metadata_quality["abduction"][finger]
                if json_path not in source_files:
                    source_files.append(json_path)
                timestamps.append(str(metadata.get("timestamp", "")))

        if not pinch_validation and metadata.get("pinch_validation"):
            pinch_validation = dict(metadata.get("pinch_validation", {}))
            component_sources["pinch_validation"] = {
                key: str(json_path) for key in pinch_validation
            }
            if json_path not in source_files:
                source_files.append(json_path)
            timestamps.append(str(metadata.get("timestamp", "")))

    if not source_files:
        calibration = fallback_calibration(
            latest_calibration_path(hand, calibration_dir),
            "no selectable calibration records found in registry",
        )
        calibration.resolver_mode = "composed_latest"
        calibration.registry_path = registry_path
        calibration.selection_summary = "no registry calibration records found"
        calibration.warnings.extend(warnings)
        return calibration

    newest_timestamp = "unknown"
    if timestamps:
        newest_timestamp = max(timestamps, key=_parse_timestamp)

    complete = (
        all(finger in flexion_ranges for finger in FINGERS)
        and all(finger in abduction_spread for finger in FINGERS)
    )
    calibration = LoadedCalibration(
        csv_path=None,
        metadata_path=None,
        hand=hand,
        mode="composed_latest",
        timestamp=newest_timestamp,
        dimensions=[
            dimension for dimension, values in (
                ("flexion", flexion_ranges),
                ("abduction", abduction_spread),
                ("pinch_validation", pinch_validation),
            ) if values
        ],
        flexion_ranges=flexion_ranges,
        abduction_spread=abduction_spread,
        pinch_validation=pinch_validation,
        complete=complete,
        partial=not complete,
        aborted=False,
        warnings=warnings,
        source="composed_registry",
        resolver_mode="composed_latest",
        source_files=source_files,
        component_sources=component_sources,
        quality=quality,
        registry_path=registry_path,
        selection_summary="composed latest calibration records",
    )
    return calibration


def load_calibration(
    csv_path: Optional[str],
    hand: str = "right",
    calibration_dir: Optional[str] = None,
    resolver_mode: str = "composed_latest",
) -> LoadedCalibration:
    if resolver_mode not in RESOLVER_MODES:
        resolver_mode = "composed_latest"

    default_dir = Path(calibration_dir).expanduser() if calibration_dir else None
    if csv_path:
        return _load_explicit_calibration(
            Path(csv_path).expanduser(),
            "explicit_file",
        )

    if resolver_mode == "explicit_file":
        path, fallback_warning = default_calibration_path_with_legacy_fallback(
            hand=hand,
            calibration_dir=default_dir,
        )
        return _load_explicit_calibration(
            path,
            "explicit_file",
            fallback_warning=fallback_warning,
        )

    if resolver_mode == "latest_complete":
        return _resolve_latest_complete(hand, default_dir)

    return _resolve_composed_latest(hand, default_dir)


def infer_calibration_from_csv(csv_path: Path) -> LoadedCalibration:
    calibration = LoadedCalibration(
        csv_path=csv_path,
        metadata_path=matching_metadata_path(csv_path),
        source="file",
        complete=False,
        partial=True,
    )

    try:
        with csv_path.open(newline="") as f:
            rows = list(csv.DictReader(f))
    except OSError as exc:
        return fallback_calibration(csv_path, f"could not read csv: {exc}")

    by_pose = {row.get("pose", ""): row for row in rows if row.get("status", "accepted") == "accepted"}
    open_row = by_pose.get("flexion_open_reference") or by_pose.get("flexion_open") or by_pose.get("open_relaxed")

    if open_row:
        for finger in FINGERS:
            closed_row = (
                by_pose.get(f"flexion_{finger}_closed")
                or by_pose.get("flexion_fist_reference")
                or by_pose.get("full_fist")
            )
            if closed_row:
                try:
                    calibration.flexion_ranges[finger] = CalibrationRange(
                        float(open_row[f"flex_{finger}"]),
                        float(closed_row[f"flex_{finger}"]),
                    )
                except (KeyError, TypeError, ValueError):
                    pass

    neutral_row = by_pose.get("abduction_neutral_together") or by_pose.get("abduction_together")
    full_splay_row = by_pose.get("abduction_full_splay")
    thumb_row = by_pose.get("thumb_radial_abduction_max") or full_splay_row
    if neutral_row and full_splay_row:
        for finger in FINGERS:
            ref_row = thumb_row if finger == "thumb" and thumb_row else full_splay_row
            try:
                neutral = float(neutral_row[f"abd_{finger}"])
                reference = float(ref_row[f"abd_{finger}"])
                calibration.abduction_spread[finger] = AbductionSpreadRange(
                    neutral_raw=neutral,
                    reference_raw=reference,
                    max_spread_delta=abs(reference - neutral),
                )
            except (KeyError, TypeError, ValueError):
                pass

    if not calibration.has_any_file_data():
        return fallback_calibration(csv_path, "csv contained no recognizable calibration rows")

    return calibration


def ranges_to_metadata(ranges: Dict[str, CalibrationRange], labels: Tuple[str, str]) -> dict:
    zero_label, one_label = labels
    return {
        finger: {
            zero_label: calibration_range.zero_raw,
            one_label: calibration_range.one_raw,
            "zero_raw": calibration_range.zero_raw,
            "one_raw": calibration_range.one_raw,
        }
        for finger, calibration_range in ranges.items()
    }


def spreads_to_metadata(spreads: Dict[str, AbductionSpreadRange]) -> dict:
    return {
        finger: {
            "neutral_raw": spread.neutral_raw,
            "reference_raw": spread.reference_raw,
            "max_spread_delta": spread.max_spread_delta,
        }
        for finger, spread in spreads.items()
    }
