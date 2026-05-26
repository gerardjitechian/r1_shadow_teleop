#!/usr/bin/env python3

import csv
import json
import shutil
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from threading import Lock

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
except ImportError:
    Console = None
    Panel = None
    Progress = None
    BarColumn = None
    TextColumn = None
    TimeRemainingColumn = None

from r1_shadow_teleop.r1_calibration import (
    DEFAULT_CALIBRATION_DIR,
    FINGERS,
    AbductionSpreadRange,
    CalibrationRange,
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


class TerminalUI:
    def __init__(self, stream=None, use_rich=True):
        self.stream = stream or sys.stdout
        self.console = None
        if (
            use_rich
            and Console is not None
            and hasattr(self.stream, "isatty")
            and self.stream.isatty()
        ):
            self.console = Console()

    def write(self, message=""):
        if self.console is not None:
            self.console.print(message)
        else:
            print(message)

    def rule(self, title: str):
        if self.console is not None:
            self.console.rule(title)
            return
        print()
        print(title)
        print("=" * len(title))

    def panel(self, title: str, lines):
        body = "\n".join(lines)
        if self.console is not None and Panel is not None:
            self.console.print(Panel(body, title=title))
            return
        self.rule(title)
        print(body)

    def warning(self, message: str):
        if self.console is not None:
            self.console.print(f"[yellow]warning:[/] {message}")
        else:
            print(f"warning: {message}")

    def progress(self, label: str, seconds: float, sleep_fn=time.sleep):
        run_timed_progress(label, seconds, self, sleep_fn=sleep_fn)


def terminal_ui() -> TerminalUI:
    return TerminalUI()


def run_timed_progress(
    label: str,
    seconds: float,
    ui: TerminalUI,
    sleep_fn=time.sleep,
    tick_seconds: float = 0.1,
):
    duration = max(0.0, float(seconds))
    if duration <= 0.0:
        ui.write(f"{label} for 0.0s...")
        return

    if ui.console is None or Progress is None:
        ui.write(f"{label} for {duration:.1f}s...")
        sleep_fn(duration)
        return

    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=ui.console,
        transient=True,
    )
    elapsed = 0.0
    with progress:
        task = progress.add_task(f"{label} ({duration:.1f}s)", total=duration)
        while elapsed < duration:
            step = min(tick_seconds, duration - elapsed)
            sleep_fn(step)
            elapsed += step
            progress.update(task, completed=elapsed)


class AbortCalibration(Exception):
    pass


class R1CalibrationNode(Node):
    def __init__(self):
        super().__init__("r1_calibration")

        self.declare_parameter("glove_topic", "/r1/glove69/rh/glove_states")
        self.declare_parameter("hand", "right")
        self.declare_parameter("calibration_mode", "both")
        self.declare_parameter("fingers", "all")
        self.declare_parameter("settle_seconds", 1.0)
        self.declare_parameter("sample_seconds", 3.0)
        self.declare_parameter("output_dir", str(DEFAULT_CALIBRATION_DIR))
        self.declare_parameter("output_name", "")
        self.declare_parameter("non_interactive", False)

        self.glove_topic = self.get_parameter("glove_topic").value
        self.samples = []
        self.lock = Lock()

        self.create_subscription(
            R1GloveState,
            self.glove_topic,
            self.on_msg,
            10,
        )

        self.get_logger().info(f"Listening to {self.glove_topic}")

    def on_msg(self, msg):
        values = list(msg.normalized_finger_positions)
        if len(values) >= 10:
            scaled = [float(v) / 10000.0 for v in values[:10]]
            with self.lock:
                self.samples.append(scaled)
                self.samples = self.samples[-2000:]

    def clear_samples(self):
        with self.lock:
            self.samples = []

    def get_recent_stats(self, settle_seconds: float, sample_seconds: float, ui=None):
        active_ui = ui or terminal_ui()
        self.clear_samples()
        active_ui.progress("Settling", settle_seconds)
        self.clear_samples()
        active_ui.progress("Sampling", sample_seconds)

        with self.lock:
            data = list(self.samples)

        if not data:
            return None, None, 0

        cols = list(zip(*data))
        means = [statistics.mean(col) for col in cols]
        stddevs = [statistics.pstdev(col) if len(col) > 1 else 0.0 for col in cols]
        return means, stddevs, len(data)


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


def ask_value(prompt: str, default: str, parser, valid_hint: str, ui=None):
    active_ui = ui or terminal_ui()
    while True:
        value = input(f"{prompt} [{default}]: ").strip() or default
        try:
            return parser(value)
        except ValueError as exc:
            active_ui.warning(str(exc))
            active_ui.write(valid_hint)


def ask_string(prompt: str, default: str) -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def collect_config(node: R1CalibrationNode, ui=None):
    active_ui = ui or terminal_ui()
    non_interactive = bool(node.get_parameter("non_interactive").value)

    raw_hand = str(node.get_parameter("hand").value)
    raw_mode = str(node.get_parameter("calibration_mode").value)
    raw_fingers = str(node.get_parameter("fingers").value)
    output_dir = str(node.get_parameter("output_dir").value)
    output_name = str(node.get_parameter("output_name").value)
    settle_seconds = float(node.get_parameter("settle_seconds").value)
    sample_seconds = float(node.get_parameter("sample_seconds").value)

    if non_interactive:
        return {
            "hand": parse_hand(raw_hand),
            "mode": parse_mode(raw_mode),
            "fingers": parse_fingers(raw_fingers),
            "settle_seconds": settle_seconds,
            "sample_seconds": sample_seconds,
            "output_dir": Path(output_dir).expanduser(),
            "output_name": output_name.strip(),
            "non_interactive": non_interactive,
        }

    active_ui.panel("R1 calibration", [
        "Records one glove at a time from normalized_finger_positions.",
        "Short aliases are accepted. Leave a prompt blank to accept its default.",
        "Use comfortable hand poses only; stop if anything feels strained.",
    ])
    hand = ask_value(
        "Hand/glove to calibrate: r/right or l/left",
        raw_hand or "right",
        parse_hand,
        "Use r/right or l/left.",
        ui=active_ui,
    )
    mode = ask_value(
        "Calibration mode: f/flexion, a/abduction, b/both, p/pinch_validation",
        raw_mode or "both",
        parse_mode,
        "Use f/flexion, a/abduction, b/both, or p/pinch_validation.",
        ui=active_ui,
    )
    fingers = ask_value(
        "Fingers: all or comma-separated t,i,m,r,p",
        raw_fingers or "all",
        parse_fingers,
        "Use all or comma-separated t/thumb, i/index, m/middle, r/ring, p/pinky.",
        ui=active_ui,
    )
    output_dir = ask_string("Output directory", output_dir or str(DEFAULT_CALIBRATION_DIR))
    output_name = ask_string("Output filename stem, blank for timestamped default", output_name)

    return {
        "hand": hand,
        "mode": mode,
        "fingers": fingers,
        "settle_seconds": settle_seconds,
        "sample_seconds": sample_seconds,
        "output_dir": Path(output_dir).expanduser(),
        "output_name": output_name.strip(),
        "non_interactive": non_interactive,
    }


def pose_text(pose, index=None, total=None, ui=None):
    active_ui = ui or terminal_ui()
    title = pose["title"]
    if index is not None and total is not None:
        title = f"Step {index}/{total}: {title}"
    active_ui.panel(title, pose["instructions"])
    input("Press Enter when ready. Settle and sampling start after you press Enter...")


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


def summarize_capture(means, stddevs, sample_count, warnings, ui=None):
    active_ui = ui or terminal_ui()
    values = dict(zip(FINGER_COLUMNS, means))
    stds = dict(zip(STD_COLUMNS, stddevs))
    active_ui.write("  captured:")
    active_ui.write(
        "  flex mean "
        f"T={values['flex_thumb']:.3f} I={values['flex_index']:.3f} "
        f"M={values['flex_middle']:.3f} R={values['flex_ring']:.3f} "
        f"P={values['flex_pinky']:.3f}"
    )
    active_ui.write(
        "  abd  mean "
        f"T={values['abd_thumb']:.3f} I={values['abd_index']:.3f} "
        f"M={values['abd_middle']:.3f} R={values['abd_ring']:.3f} "
        f"P={values['abd_pinky']:.3f}"
    )
    max_std = max(stds.values()) if stds else 0.0
    active_ui.write(f"  samples={sample_count} max_std={max_std:.3f}")
    for warning in warnings:
        active_ui.warning(warning)


def decision_for_pose(optional: bool):
    valid = "Enter/a=accept, r=repeat, q=abort"
    if optional:
        valid = "Enter/a=accept, r=repeat, s=skip, q=abort"
    while True:
        choice = input(f"Action ({valid}): ").strip().lower()
        if choice in {"", "a", "accept"}:
            return "accepted"
        if choice in {"r", "repeat"}:
            return "repeat"
        if optional and choice in {"s", "skip"}:
            return "skipped"
        if choice in {"q", "quit", "abort"}:
            raise AbortCalibration()
        print(f"Invalid action {choice!r}. Use {valid}.")


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


def record_pose(node: R1CalibrationNode, config, pose, index=None, total=None, ui=None):
    active_ui = ui or terminal_ui()
    attempt = 1
    while True:
        pose_text(pose, index=index, total=total, ui=active_ui)
        means, stddevs, sample_count = node.get_recent_stats(
            config["settle_seconds"],
            config["sample_seconds"],
            ui=active_ui,
        )

        if means is None:
            warnings = ["no data received"]
            active_ui.warning("No data received for this pose.")
            decision = decision_for_pose(optional=pose.get("optional", False))
            if decision == "repeat":
                attempt += 1
                continue
            return blank_row(config, pose, decision, attempt, warnings)

        warnings = sample_warnings(pose, means, stddevs, sample_count)
        summarize_capture(means, stddevs, sample_count, warnings, ui=active_ui)
        decision = decision_for_pose(optional=pose.get("optional", False))
        if decision == "repeat":
            attempt += 1
            continue
        return row_from_sample(
            config,
            pose,
            means,
            stddevs,
            sample_count,
            decision,
            attempt,
            warnings,
        )


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


def main(args=None):
    ui = terminal_ui()
    rclpy.init(args=args)
    node = R1CalibrationNode()
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,))
    spin_thread.start()
    rows = []
    config = None
    aborted = False

    try:
        config = collect_config(node, ui=ui)
        poses = selected_poses(config["mode"], config["fingers"])

        ui.panel("Calibration run", [
            f"Hand: {config['hand']}",
            f"Mode: {config['mode']}",
            f"Fingers: {','.join(config['fingers'])}",
            f"Settle seconds: {config['settle_seconds']:.1f}",
            f"Sample seconds: {config['sample_seconds']:.1f}",
            f"Output directory: {config['output_dir']}",
        ])

        total_poses = len(poses)
        for index, pose in enumerate(poses, start=1):
            row = record_pose(
                node,
                config,
                pose,
                index=index,
                total=total_poses,
                ui=ui,
            )
            row["optional_pose"] = pose.get("optional", False)
            rows.append(row)

    except (KeyboardInterrupt, AbortCalibration):
        aborted = True
        ui.warning("Calibration aborted safely. Accepted rows will be saved as incomplete.")
    except ValueError as exc:
        aborted = True
        ui.warning(f"Invalid calibration settings: {exc}")
    finally:
        try:
            if config and rows:
                csv_path, json_path, latest_csv, latest_json, metadata = write_outputs(
                    config,
                    rows,
                    aborted=aborted,
                )
                saved_lines = [
                    f"CSV:  {csv_path}",
                    f"JSON: {json_path}",
                    f"Complete: {metadata['complete']}",
                ]
                if latest_csv and latest_json:
                    saved_lines.extend([
                        f"Latest CSV:  {latest_csv}",
                        f"Latest JSON: {latest_json}",
                    ])
                else:
                    saved_lines.append(
                        "Latest files not updated because calibration is incomplete or aborted."
                    )
                ui.panel("Calibration saved", saved_lines)
                for warning in metadata["warnings"][:8]:
                    ui.warning(warning)
            elif config:
                ui.warning("No calibration data captured; no files written.")
        finally:
            rclpy.shutdown()
            spin_thread.join(timeout=2.0)
            node.destroy_node()


if __name__ == "__main__":
    main()
