#!/usr/bin/env python3

import statistics
import threading
from pathlib import Path
from threading import Lock

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState

from r1_shadow_teleop.calibration.capture import (
    FINGER_COLUMNS,
    STD_COLUMNS,
    blank_row,
    row_from_sample,
    sample_warnings,
    write_outputs,
)
from r1_shadow_teleop.calibration.defaults import DEFAULT_CALIBRATION_DIR
from r1_shadow_teleop.calibration.poses import (
    parse_fingers,
    parse_hand,
    parse_mode,
    selected_poses,
)
from r1_shadow_teleop.calibration.terminal_ui import terminal_ui


class AbortCalibration(Exception):
    pass


class R1CalibrationNode(Node):
    def __init__(self):
        super().__init__("senseglove_r1_calibration")

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
