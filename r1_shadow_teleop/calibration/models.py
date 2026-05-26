from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


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
