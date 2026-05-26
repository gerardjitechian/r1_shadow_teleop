#!/usr/bin/env python3

import sys

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState

from r1_shadow_teleop.r1_calibration import (
    DEFAULT_CALIBRATION_DIR,
    abduction_diagnostics,
    calibrate_flexion,
    load_calibration,
)
from r1_shadow_teleop.r1_hand_frame import FINGER_ORDER, parse_r1_glove_state
from r1_shadow_teleop.shadow_mapping import map_r1_flexion_to_shadow_targets
from r1_shadow_teleop.shadow_trajectory import build_shadow_joint_trajectory
from r1_shadow_teleop.shadow_command_packet import trajectory_to_packet, save_packet

try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    Console = None
    Group = None
    Live = None
    Panel = None
    Table = None
    Text = None


LATEST_PACKET_PATH = (
    "/home/gerard/r1_ws/src/r1_shadow_teleop/docs/latest_shadow_command_packet.json"
)


class R1GloveListener(Node):
    def __init__(self):
        super().__init__("r1_glove_listener")

        self.declare_parameter("glove_topic", "/r1/glove69/rh/glove_states")
        self.declare_parameter("print_period_sec", 1.0)
        self.declare_parameter("compact_output", True)
        self.declare_parameter("show_shadow_targets", False)
        self.declare_parameter("color_output", True)
        self.declare_parameter("use_rich", True)
        self.declare_parameter("calibration_dir", str(DEFAULT_CALIBRATION_DIR))
        self.declare_parameter("calibration_csv_path", "")
        self.declare_parameter("calibration_resolver_mode", "composed_latest")

        self.glove_topic = self.get_parameter("glove_topic").value
        self.print_period_sec = self.get_parameter("print_period_sec").value
        self.compact_output = bool(self.get_parameter("compact_output").value)
        self.show_shadow_targets = bool(
            self.get_parameter("show_shadow_targets").value
        )
        self.color_output = bool(self.get_parameter("color_output").value)
        self.use_rich = bool(self.get_parameter("use_rich").value)
        self.calibration_dir = self.get_parameter("calibration_dir").value
        self.calibration_csv_path = self.get_parameter("calibration_csv_path").value
        self.calibration_resolver_mode = self.get_parameter(
            "calibration_resolver_mode"
        ).value
        self.calibration = load_calibration(
            self.calibration_csv_path,
            calibration_dir=self.calibration_dir,
            resolver_mode=self.calibration_resolver_mode,
        )

        self.latest_msg = None
        self.latest_frame = None
        self.message_count = 0
        self.console = Console() if Console is not None and self.use_rich else None
        self.live = None

        self.create_subscription(
            R1GloveState,
            self.glove_topic,
            self.on_glove_state,
            10,
        )

        self.create_timer(self.print_period_sec, self.print_summary)

        self.get_logger().info(f"Listening to R1 glove topic: {self.glove_topic}")
        self.get_logger().info("\n".join(self.calibration_lines()))

    def close_dashboard(self):
        if self.live is not None:
            self.live.stop()
            self.live = None

    def on_glove_state(self, msg: R1GloveState):
        self.latest_msg = msg
        self.message_count += 1
        self.latest_frame = parse_r1_glove_state(
            msg,
            source_topic=self.glove_topic,
            message_count=self.message_count,
        )

    def print_summary(self):
        if self.latest_frame is None:
            message = f"Waiting for glove messages on {self.glove_topic}"
            if self.compact_output:
                self.render_waiting_dashboard(message)
            else:
                self.get_logger().info(message)
            return

        raw_flexion = self.latest_frame.raw_flexion_by_finger()
        raw_abduction = self.latest_frame.raw_abduction_by_finger()
        flexion_ranges = (
            self.calibration.flexion_ranges
            if self.calibration.has_complete_flexion()
            else None
        )
        calibrated_flexion = calibrate_flexion(raw_flexion, ranges=flexion_ranges)
        abduction_status = abduction_diagnostics(raw_abduction, self.calibration)

        target = map_r1_flexion_to_shadow_targets(calibrated_flexion)
        trajectory_msg = build_shadow_joint_trajectory(target, duration_sec=2.0)
        packet = trajectory_to_packet(trajectory_msg)
        save_packet(packet, LATEST_PACKET_PATH)

        if self.compact_output:
            self.render_dashboard(
                raw_flexion,
                calibrated_flexion,
                raw_abduction,
                abduction_status,
                target,
            )
        else:
            self.get_logger().info(
                "\n".join(
                    self.dashboard_lines(
                        raw_flexion,
                        calibrated_flexion,
                        raw_abduction,
                        abduction_status,
                        target,
                    )
                )
            )

    def render_waiting_dashboard(self, message: str) -> None:
        if self.can_use_rich():
            self.update_live(
                Panel(
                    "\n".join([message, "", *self.calibration_lines()]),
                    title="R1 Shadow Teleop",
                )
            )
            return

        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write(f"R1 Shadow Teleop\n{message}\n")
        sys.stdout.write("\n".join(self.calibration_lines()) + "\n")
        sys.stdout.flush()

    def can_use_rich(self) -> bool:
        return (
            self.console is not None
            and Live is not None
            and Table is not None
            and Panel is not None
        )

    def update_live(self, renderable) -> None:
        if self.live is None:
            self.live = Live(renderable, console=self.console, refresh_per_second=4)
            self.live.start()
        else:
            self.live.update(renderable)

    def render_dashboard(
        self,
        raw_flexion,
        calibrated_flexion,
        raw_abduction,
        abduction_status,
        target,
    ) -> None:
        if self.can_use_rich():
            self.update_live(
                self.rich_dashboard(
                    raw_flexion,
                    calibrated_flexion,
                    raw_abduction,
                    abduction_status,
                    target,
                )
            )
            return

        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write(
            "\n".join(
                self.dashboard_lines(
                    raw_flexion,
                    calibrated_flexion,
                    raw_abduction,
                    abduction_status,
                    target,
                )
            )
        )
        sys.stdout.write("\n")
        sys.stdout.flush()

    def rich_dashboard(
        self,
        raw_flexion,
        calibrated_flexion,
        raw_abduction,
        abduction_status,
        target,
    ):
        header = Panel(
            "\n".join([*self.status_lines(), "", *self.calibration_lines()]),
            title="R1 -> Shadow dry-run dashboard",
        )
        table = Table(title="R1 finger values")
        table.add_column("finger")
        table.add_column("raw flex", justify="right")
        table.add_column("cal flex", justify="right")
        table.add_column("raw/sdk abd", justify="right")
        table.add_column("neutral", justify="right")
        table.add_column("abd offset", justify="right")
        table.add_column("spread", justify="right")
        table.add_column("abd status")
        table.add_column("force mN", justify="right")
        table.add_column("thumb dist mm", justify="right")

        for finger in FINGER_ORDER:
            pose = self.latest_frame.fingers[finger]
            table.add_row(
                finger,
                self.format_value(raw_flexion.get(finger, 0.0)),
                self.format_calibrated(calibrated_flexion.get(finger, 0.0)),
                self.format_value(raw_abduction.get(finger, 0.0)),
                self.format_diagnostic_value(abduction_status[finger].neutral_raw),
                self.format_diagnostic_signed(abduction_status[finger].signed_offset),
                self.format_spread(abduction_status[finger]),
                abduction_status[finger].status,
                self.format_optional(pose.sensed_force_mn),
                self.format_optional(pose.thumb_distance_mm),
            )

        footer = (
            "raw/sdk abduction is directional; spread is shown only when "
            "calibration metadata is reliable"
        )
        items = [header, table, footer]
        if self.show_shadow_targets:
            items.append(self.shadow_target_table(target))
        return Group(*items) if Group is not None else table

    def shadow_target_table(self, target):
        table = Table(title="Shadow target preview, NOT publishing")
        table.add_column("joint")
        table.add_column("position", justify="right")

        for name, position in zip(target.joint_names, target.positions):
            table.add_row(name, self.format_value(position))

        return table

    def dashboard_lines(
        self,
        raw_flexion,
        calibrated_flexion,
        raw_abduction,
        abduction_status,
        target,
    ):
        lines = [
            "R1 -> Shadow dry-run dashboard",
            *self.status_lines(),
            "",
            *self.calibration_lines(),
            "",
            (
                "raw/sdk abduction is directional; spread is shown only when "
                "calibration metadata is reliable"
            ),
            "",
            (
                "finger | raw flex | cal flex | raw abd | neutral | abd off | "
                "spread | abd status | force mN | thumb dist mm"
            ),
            (
                "-------+----------+----------+---------+---------+---------+"
                "--------+------------+----------+--------------"
            ),
        ]

        for finger in FINGER_ORDER:
            pose = self.latest_frame.fingers[finger]
            diagnostic = abduction_status[finger]
            neutral_text = self.format_diagnostic_value(diagnostic.neutral_raw)
            offset_text = self.format_diagnostic_signed(diagnostic.signed_offset)
            spread_text = self.format_spread_text(diagnostic)
            lines.append(
                f"{finger:>6} | "
                f"{self.format_value(raw_flexion.get(finger, 0.0)):>8} | "
                f"{self.format_value(calibrated_flexion.get(finger, 0.0)):>8} | "
                f"{self.format_value(raw_abduction.get(finger, 0.0)):>7} | "
                f"{neutral_text:>7} | "
                f"{offset_text:>7} | "
                f"{spread_text:>6} | "
                f"{diagnostic.status:>10} | "
                f"{self.format_optional(pose.sensed_force_mn):>8} | "
                f"{self.format_optional(pose.thumb_distance_mm):>12}"
            )

        if self.show_shadow_targets:
            lines.extend(["", "Shadow target preview, NOT publishing:"])
            for name, position in zip(target.joint_names, target.positions):
                lines.append(f"  {name}: {position: .3f}")

        return lines

    def status_lines(self):
        return [
            f"topic: {self.glove_topic}",
            f"messages_received: {self.message_count}",
            f"packet: {LATEST_PACKET_PATH}",
            "safety: dry-run only, not publishing to Shadow",
        ]

    def calibration_lines(self):
        lines = [
            f"Calibration resolver: {self.calibration.resolver_mode}",
            f"Calibration source: {self.calibration_source_label()}",
            f"Calibration files: {self.calibration.source_files_summary()}",
            f"Calibration components: {self.calibration.component_sources_summary()}",
        ]
        if self.calibration.registry_path is not None:
            lines.append(f"Calibration registry: {self.calibration.registry_path}")
        lines.extend([
            f"Calibration timestamp: {self.calibration.timestamp}",
            f"Calibration hand: {self.calibration.hand}",
            (
                "Calibration dimensions: "
                f"{','.join(self.calibration.dimensions) or 'fallback'}"
            ),
            f"Calibration contents: {self.calibration.contents_summary()}",
            f"Calibration status: {self.calibration.diagnostic_status()}",
            f"Calibration detail: {self.calibration.status_summary()}",
        ])
        warnings = self.calibration_reporting_warnings()
        if warnings:
            lines.append("Calibration warnings: " + "; ".join(warnings))
        return lines

    def calibration_source_label(self):
        source_kind = self.calibration.source
        if source_kind == "composed_registry":
            return "composed from registry"
        if source_kind == "latest_complete_registry":
            return "latest complete registry record"
        if source_kind == "explicit_file":
            if self.calibration.is_latest_path():
                return "latest explicit file"
            return "explicit schema v2 file"
        if source_kind == "legacy_csv_only":
            return "legacy CSV-only, recalibration recommended"
        if source_kind == "fallback":
            return "fallback, recalibration recommended"
        return source_kind

    def calibration_reporting_warnings(self):
        warnings = list(self.calibration.warnings)
        if not self.calibration.uses_schema_v2_metadata():
            warnings.append("schema v2 metadata unavailable; recalibration recommended")
        missing_quality = [
            finger for finger in self.calibration.abduction_fingers()
            if finger not in self.calibration.quality.get("abduction", {})
        ]
        if missing_quality:
            warnings.append(
                "abduction quality metadata missing for "
                + ",".join(missing_quality)
                + "; recalibration recommended"
            )
        unique = []
        for warning in warnings:
            if warning and warning not in unique:
                unique.append(warning)
        return unique

    @staticmethod
    def format_value(value: float) -> str:
        return f"{float(value):.3f}"

    @staticmethod
    def format_signed(value: float) -> str:
        return f"{float(value):+.3f}"

    def format_calibrated(self, value: float):
        text = self.format_value(value)
        if not self.color_output or Text is None:
            return text

        numeric = float(value)
        if numeric < 0.34:
            style = "green"
        elif numeric < 0.67:
            style = "yellow"
        else:
            style = "red"
        return Text(text, style=style)

    @staticmethod
    def format_diagnostic_value(value) -> str:
        if value is None:
            return "--"
        return f"{float(value):.3f}"

    @staticmethod
    def format_diagnostic_signed(value) -> str:
        if value is None:
            return "--"
        return f"{float(value):+.3f}"

    def format_spread(self, diagnostic):
        text = self.format_spread_text(diagnostic)
        if not diagnostic.reliable or not self.color_output or Text is None:
            return text
        return self.format_calibrated(diagnostic.spread)

    @staticmethod
    def format_spread_text(diagnostic) -> str:
        if not diagnostic.reliable or diagnostic.spread is None:
            return "--"
        return f"{float(diagnostic.spread):.3f}"

    @staticmethod
    def format_optional(value) -> str:
        if value is None:
            return "--"
        return f"{float(value):.1f}"


def main(args=None):
    rclpy.init(args=args)
    node = R1GloveListener()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.close_dashboard()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
