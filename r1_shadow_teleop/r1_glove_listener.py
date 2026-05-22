#!/usr/bin/env python3

from typing import Any, Dict

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState

from r1_shadow_teleop.shadow_mapping import map_r1_flexion_to_shadow_targets


class R1GloveListener(Node):
    def __init__(self):
        super().__init__("r1_glove_listener")

        self.declare_parameter("glove_topic", "/r1/glove69/rh/glove_states")
        self.declare_parameter("print_period_sec", 1.0)

        self.glove_topic = (
            self.get_parameter("glove_topic")
            .get_parameter_value()
            .string_value
        )

        self.print_period_sec = (
            self.get_parameter("print_period_sec")
            .get_parameter_value()
            .double_value
        )

        self.latest_msg = None
        self.message_count = 0

        self.subscription = self.create_subscription(
            R1GloveState,
            self.glove_topic,
            self.on_glove_state,
            10,
        )

        self.timer = self.create_timer(
            self.print_period_sec,
            self.print_summary,
        )

        self.get_logger().info(f"Listening to R1 glove topic: {self.glove_topic}")

    def on_glove_state(self, msg: R1GloveState):
        self.latest_msg = msg
        self.message_count += 1

    def ros_value_to_python(self, value: Any):
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        # MultiArray messages have .data
        if hasattr(value, "data"):
            return list(value.data)

        # ROS2 float64[] fields often appear as array.array, not list
        if hasattr(value, "__iter__") and not isinstance(value, (str, bytes, dict)):
            try:
                return [self.ros_value_to_python(v) for v in value]
            except TypeError:
                pass

        # Nested ROS messages
        if hasattr(value, "get_fields_and_field_types"):
            out = {}
            for field_name in value.get_fields_and_field_types().keys():
                out[field_name] = self.ros_value_to_python(getattr(value, field_name))
            return out

        return str(value)

    def get_field(self, msg: R1GloveState, field_name: str):
        if hasattr(msg, field_name):
            return self.ros_value_to_python(getattr(msg, field_name))
        return None

    def infer_flexion_by_finger(self, msg: R1GloveState) -> Dict[str, float]:
        """
        R1 normalized_finger_positions order from the message definition:

        [flexion_thumb, flexion_index, flexion_middle, flexion_ring, flexion_pinky,
         abduction_thumb, abduction_index, abduction_middle, abduction_ring, abduction_pinky]

        Range is 0..10000, so we divide by 10000 for 0.0..1.0.
        """
        values = self.get_field(msg, "normalized_finger_positions")

        if not isinstance(values, list) or len(values) < 5:
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

        msg = self.latest_msg
        raw_positions = self.get_field(msg, "normalized_finger_positions")
        flexion_by_finger = self.infer_flexion_by_finger(msg)
        target = map_r1_flexion_to_shadow_targets(flexion_by_finger)

        lines = [
            "",
            "R1 → Shadow dry-run mapping",
            f"  topic: {self.glove_topic}",
            f"  messages_received: {self.message_count}",
            f"  raw normalized_finger_positions: {raw_positions}",
            "  R1 flexion estimate, scaled 0.0..1.0:",
        ]

        for finger, value in flexion_by_finger.items():
            lines.append(f"    {finger:>6}: {value: .3f}")

        lines.append("  Proposed Shadow joint targets, NOT publishing:")
        for name, pos in zip(target.joint_names, target.positions):
            lines.append(f"    {name}: {pos: .3f}")

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
