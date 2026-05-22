#!/usr/bin/env python3

from typing import Any, Dict

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState

from r1_shadow_teleop.r1_calibration import calibrate_flexion
from r1_shadow_teleop.shadow_mapping import map_r1_flexion_to_shadow_targets
from r1_shadow_teleop.shadow_trajectory import build_shadow_joint_trajectory, format_joint_trajectory


class R1GloveListener(Node):
    def __init__(self):
        super().__init__("r1_glove_listener")

        self.declare_parameter("glove_topic", "/r1/glove69/rh/glove_states")
        self.declare_parameter("print_period_sec", 1.0)

        self.glove_topic = self.get_parameter("glove_topic").value
        self.print_period_sec = self.get_parameter("print_period_sec").value

        self.latest_msg = None
        self.message_count = 0

        self.create_subscription(
            R1GloveState,
            self.glove_topic,
            self.on_glove_state,
            10,
        )

        self.create_timer(self.print_period_sec, self.print_summary)

        self.get_logger().info(f"Listening to R1 glove topic: {self.glove_topic}")

    def on_glove_state(self, msg: R1GloveState):
        self.latest_msg = msg
        self.message_count += 1

    def get_raw_flexion_by_finger(self, msg: R1GloveState) -> Dict[str, float]:
        values = list(msg.normalized_finger_positions)

        if len(values) < 5:
            return {
                "thumb": 0.0,
                "index": 0.0,
                "middle": 0.0,
                "ring": 0.0,
                "pinky": 0.0,
            }

        return {
            "thumb": float(values[0]) / 10000.0,
            "index": float(values[1]) / 10000.0,
            "middle": float(values[2]) / 10000.0,
            "ring": float(values[3]) / 10000.0,
            "pinky": float(values[4]) / 10000.0,
        }

    def print_summary(self):
        if self.latest_msg is None:
            self.get_logger().info(
                f"No glove messages received yet on {self.glove_topic}"
            )
            return

        raw_flexion = self.get_raw_flexion_by_finger(self.latest_msg)
        calibrated_flexion = calibrate_flexion(raw_flexion)

        target = map_r1_flexion_to_shadow_targets(calibrated_flexion)
        trajectory_msg = build_shadow_joint_trajectory(target, duration_sec=2.0)

        lines = [
            "",
            "R1 → Shadow calibrated dry-run mapping",
            f"  topic: {self.glove_topic}",
            f"  messages_received: {self.message_count}",
            "  Raw R1 flexion, scaled 0.0..1.0:",
        ]

        for finger, value in raw_flexion.items():
            lines.append(f"    {finger:>6}: {value: .3f}")

        lines.append("  Calibrated R1 flexion, open≈0.0 closed≈1.0:")

        for finger, value in calibrated_flexion.items():
            lines.append(f"    {finger:>6}: {value: .3f}")

        ff_flex = calibrated_flexion.get("index", 0.0)
        rf_flex = calibrated_flexion.get("ring", 0.0)
        th_flex = calibrated_flexion.get("thumb", 0.0)

        lines.append("  Human-readable Shadow preview:")
        lines.append(f"    Shadow first finger from R1 index: {ff_flex: .3f}")
        lines.append(f"    Shadow ring finger  from R1 ring:  {rf_flex: .3f}")
        lines.append(f"    Shadow thumb        from R1 thumb: {th_flex: .3f}")

        lines.append("  Proposed Shadow joint targets, NOT publishing:")

        for name, pos in zip(target.joint_names, target.positions):
            lines.append(f"    {name}: {pos: .3f}")

        lines.append("")
        lines.append(format_joint_trajectory(trajectory_msg))

        self.get_logger().info("\n".join(lines))


def main(args=None):
    rclpy.init(args=args)
    node = R1GloveListener()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
