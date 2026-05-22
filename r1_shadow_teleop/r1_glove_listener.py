#!/usr/bin/env python3

from typing import Any

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState


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
        """
        Convert common ROS message fields into printable Python values.
        Handles scalars, lists, tuples, arrays, and nested ROS messages.
        """
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, (list, tuple)):
            converted = [self.ros_value_to_python(v) for v in value]
            if len(converted) > 10:
                return converted[:10] + ["..."]
            return converted

        # std_msgs/*MultiArray types usually have a .data field.
        if hasattr(value, "data"):
            data = list(value.data)
            if len(data) > 10:
                return data[:10] + ["..."]
            return data

        # Nested ROS messages expose get_fields_and_field_types().
        if hasattr(value, "get_fields_and_field_types"):
            out = {}
            for field_name in value.get_fields_and_field_types().keys():
                out[field_name] = self.ros_value_to_python(
                    getattr(value, field_name)
                )
            return out

        return str(value)

    def get_field(self, msg: R1GloveState, field_name: str):
        if hasattr(msg, field_name):
            return self.ros_value_to_python(getattr(msg, field_name))
        return None

    def print_summary(self):
        if self.latest_msg is None:
            self.get_logger().info(
                f"No glove messages received yet on {self.glove_topic}"
            )
            return

        msg = self.latest_msg
        fields = list(msg.get_fields_and_field_types().keys())

        self.get_logger().info(
            "\n"
            f"R1 glove summary\n"
            f"  topic: {self.glove_topic}\n"
            f"  messages_received: {self.message_count}\n"
            f"  fields: {fields}\n"
            f"  finger_names: {self.get_field(msg, 'finger_names')}\n"
            f"  joint_angles: {self.get_field(msg, 'joint_angles')}\n"
            f"  finger_distances: {self.get_field(msg, 'finger_distances')}\n"
            f"  normalized_finger_positions: {self.get_field(msg, 'normalized_finger_positions')}\n"
            f"  normalized_finger_positions_pinch: {self.get_field(msg, 'normalized_finger_positions_pinch')}\n"
            f"  sensed_forces: {self.get_field(msg, 'sensed_forces')}\n"
        )


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
