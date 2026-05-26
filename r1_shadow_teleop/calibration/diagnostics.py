from typing import Dict, List, Optional

from r1_shadow_teleop.calibration.models import (
    ABDUCTION_MIN_RELIABLE_DELTA,
    ABDUCTION_STDDEV_WARNING_THRESHOLD,
    FINGERS,
    AbductionDiagnostic,
    AbductionSpreadRange,
    CalibrationRange,
    LoadedCalibration,
    built_in_abduction_spread,
    built_in_flexion_ranges,
)


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
