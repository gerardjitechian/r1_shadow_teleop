#!/usr/bin/env python3

import csv
import statistics
import time
from pathlib import Path
from threading import Lock

import rclpy
from rclpy.node import Node

from r1_msgs.msg import R1GloveState


POSES = [
    "open_relaxed",
    "full_fist",
    "thumb_only",
    "index_only",
    "middle_only",
    "ring_only",
    "pinky_only",
    "index_thumb_pinch",
    "ring_thumb_pinch",
]


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


class R1PoseRecorder(Node):
    def __init__(self):
        super().__init__("r1_pose_recorder")

        self.declare_parameter("glove_topic", "/r1/glove69/rh/glove_states")
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
                self.samples = self.samples[-1000:]

    def clear_samples(self):
        with self.lock:
            self.samples = []

    def get_recent_average(self, seconds=2.0):
        self.clear_samples()
        time.sleep(seconds)

        with self.lock:
            data = list(self.samples)

        if not data:
            return None

        cols = list(zip(*data))
        return [statistics.mean(col) for col in cols]


def main(args=None):
    rclpy.init(args=args)
    node = R1PoseRecorder()

    import threading
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    print()
    print("R1 pose recorder")
    print("================")
    print("For each pose:")
    print("1. Move your hand into the requested pose.")
    print("2. Hold still.")
    print("3. Press Enter.")
    print("4. The script will average about 2 seconds of data.")
    print()

    output_dir = Path.home() / "r1_ws" / "src" / "r1_shadow_teleop" / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "r1_right_glove_pose_calibration.csv"

    rows = []

    try:
        for pose in POSES:
            input(f"Pose: {pose}. Hold the pose, then press Enter...")
            avg = node.get_recent_average(seconds=2.0)

            if avg is None:
                print(f"  No data received for pose {pose}")
                continue

            row = {"pose": pose}
            for name, value in zip(FINGER_COLUMNS, avg):
                row[name] = value
            rows.append(row)

            print("  captured:")
            print(
                "  flex "
                f"T={row['flex_thumb']:.3f} "
                f"I={row['flex_index']:.3f} "
                f"M={row['flex_middle']:.3f} "
                f"R={row['flex_ring']:.3f} "
                f"P={row['flex_pinky']:.3f}"
            )
            print()

        with output_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["pose"] + FINGER_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Saved calibration CSV to: {output_path}")

    except KeyboardInterrupt:
        print("Interrupted.")

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
