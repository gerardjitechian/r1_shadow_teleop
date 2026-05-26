#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState


class R1CalibrationPrinter(Node):
    def __init__(self):
        super().__init__("senseglove_r1_calibration_printer")

        self.declare_parameter("glove_topic", "/r1/glove69/rh/glove_states")
        self.declare_parameter("print_period_sec", 0.5)

        self.glove_topic = self.get_parameter("glove_topic").value
        self.print_period_sec = self.get_parameter("print_period_sec").value

        self.latest_msg = None
        self.message_count = 0

        self.create_subscription(
            R1GloveState,
            self.glove_topic,
            self.on_msg,
            10,
        )

        self.create_timer(self.print_period_sec, self.print_values)

        self.get_logger().info(f"Listening to {self.glove_topic}")

    def on_msg(self, msg):
        self.latest_msg = msg
        self.message_count += 1

    def print_values(self):
        if self.latest_msg is None:
            self.get_logger().info("waiting for glove messages...")
            return

        values = list(self.latest_msg.normalized_finger_positions)

        if len(values) < 10:
            self.get_logger().warn(
                f"Expected 10 normalized_finger_positions values, got {len(values)}"
            )
            return

        flex_thumb = values[0] / 10000.0
        flex_index = values[1] / 10000.0
        flex_middle = values[2] / 10000.0
        flex_ring = values[3] / 10000.0
        flex_pinky = values[4] / 10000.0

        abd_thumb = values[5] / 10000.0
        abd_index = values[6] / 10000.0
        abd_middle = values[7] / 10000.0
        abd_ring = values[8] / 10000.0
        abd_pinky = values[9] / 10000.0

        self.get_logger().info(
            "count={:05d} | "
            "flex T={:.3f} I={:.3f} M={:.3f} R={:.3f} P={:.3f} | "
            "abd T={:.3f} I={:.3f} M={:.3f} R={:.3f} P={:.3f}".format(
                self.message_count,
                flex_thumb,
                flex_index,
                flex_middle,
                flex_ring,
                flex_pinky,
                abd_thumb,
                abd_index,
                abd_middle,
                abd_ring,
                abd_pinky,
            )
        )


def main(args=None):
    rclpy.init(args=args)
    node = R1CalibrationPrinter()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
