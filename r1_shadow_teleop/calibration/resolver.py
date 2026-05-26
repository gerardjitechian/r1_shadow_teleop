from pathlib import Path
from typing import List, Optional, Tuple

from r1_shadow_teleop.calibration.models import FINGERS, RESOLVER_MODES, LoadedCalibration
from r1_shadow_teleop.calibration.storage import (
    _calibration_from_metadata,
    _metadata_source_csv,
    _load_explicit_calibration,
    _parse_timestamp,
    _sorted_metadata_items,
    _ranges_from_metadata,
    _spreads_from_metadata,
    candidate_sidecar_paths,
    default_calibration_path_with_legacy_fallback,
    fallback_calibration,
    latest_calibration_path,
    metadata_from_sidecar,
)


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
