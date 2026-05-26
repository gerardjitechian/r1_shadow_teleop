#!/usr/bin/env python3

"""
Shadow ROS1 JointTrajectory sender skeleton.

Default behavior:
- Read a dry-run Shadow command packet.
- Validate packet structure and joint order.
- Print what would be sent to /rh_trajectory_controller/command.
- Do NOT publish.

Publishing requires all of the following:
- --publish
- --i-understand-this-can-move-the-robot
- packet safety.publish_to_robot == true
- packet safety.dry_run_only == false

The current R1-generated packets intentionally do not satisfy those conditions.
"""

import argparse
import json
import sys
from pathlib import Path


EXPECTED_SHADOW_JOINT_NAMES = [
    "rh_FFJ1",
    "rh_FFJ2",
    "rh_FFJ3",
    "rh_FFJ4",
    "rh_RFJ1",
    "rh_RFJ2",
    "rh_RFJ3",
    "rh_RFJ4",
    "rh_THJ1",
    "rh_THJ2",
    "rh_THJ4",
    "rh_THJ5",
]


COMMAND_TOPIC = "/rh_trajectory_controller/command"


def load_packet(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Packet file does not exist: {path}")
    return json.loads(path.read_text())


def validate_packet(packet: dict) -> None:
    if packet.get("type") != "shadow_joint_trajectory_preview":
        raise ValueError(f"Unexpected packet type: {packet.get('type')}")

    trajectory = packet.get("trajectory", {})
    joint_names = trajectory.get("joint_names", [])
    positions = trajectory.get("positions", [])

    if joint_names != EXPECTED_SHADOW_JOINT_NAMES:
        raise ValueError(
            "Joint names do not match expected Shadow Hand Lite order.\n"
            f"Expected: {EXPECTED_SHADOW_JOINT_NAMES}\n"
            f"Got:      {joint_names}"
        )

    if len(positions) != len(joint_names):
        raise ValueError(
            f"Position count mismatch: {len(positions)} positions for "
            f"{len(joint_names)} joints"
        )

    for name, value in zip(joint_names, positions):
        if not isinstance(value, (int, float)):
            raise ValueError(f"Position for {name} is not numeric: {value}")


def print_preview(packet: dict) -> None:
    trajectory = packet["trajectory"]
    joint_names = trajectory["joint_names"]
    positions = trajectory["positions"]
    duration_sec = float(trajectory["duration_sec"])

    print()
    print("Shadow ROS1 sender skeleton")
    print("===========================")
    print(f"Packet time:       {packet.get('created_utc')}")
    print(f"Target topic:      {COMMAND_TOPIC}")
    print("Default behavior:  PRINT ONLY")
    print()
    print("Would construct trajectory_msgs/JointTrajectory:")
    print("  joint_names:")

    for name in joint_names:
        print(f"    - {name}")

    print("  points[0].positions:")

    for name, pos in zip(joint_names, positions):
        print(f"    {name}: {float(pos): .3f}")

    print(f"  points[0].time_from_start: {duration_sec:.3f} sec")
    print()
    print("Grouped summary:")
    print(
        "  FF / first finger: "
        f"{positions[0]:.3f}, {positions[1]:.3f}, {positions[2]:.3f}, {positions[3]:.3f}"
    )
    print(
        "  RF / ring finger:  "
        f"{positions[4]:.3f}, {positions[5]:.3f}, {positions[6]:.3f}, {positions[7]:.3f}"
    )
    print(
        "  TH / thumb:        "
        f"{positions[8]:.3f}, {positions[9]:.3f}, {positions[10]:.3f}, {positions[11]:.3f}"
    )
    print()


def packet_allows_robot_motion(packet: dict) -> bool:
    safety = packet.get("safety", {})
    return (
        safety.get("publish_to_robot") is True
        and safety.get("dry_run_only") is False
    )


def publish_ros1(packet: dict) -> None:
    """
    Import ROS1 modules only when actually publishing.

    This lets the script run in print-only mode on the ROS2 R1 machine.
    """
    import rospy
    from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
    from rospy import Duration

    trajectory = packet["trajectory"]

    msg = JointTrajectory()
    msg.joint_names = list(trajectory["joint_names"])

    point = JointTrajectoryPoint()
    point.positions = [float(x) for x in trajectory["positions"]]
    point.time_from_start = Duration.from_sec(float(trajectory["duration_sec"]))

    msg.points.append(point)

    rospy.init_node("shadow_ros1_sender_once", anonymous=True)
    pub = rospy.Publisher(COMMAND_TOPIC, JointTrajectory, queue_size=1)

    rospy.sleep(1.0)
    pub.publish(msg)
    rospy.sleep(0.5)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read a Shadow command packet and optionally publish it in ROS1."
    )

    parser.add_argument(
        "--packet",
        default="docs/latest_shadow_command_packet.json",
        help="Path to latest_shadow_command_packet.json",
    )

    parser.add_argument(
        "--publish",
        action="store_true",
        help="Actually publish to ROS1. Disabled unless safety gates pass.",
    )

    parser.add_argument(
        "--i-understand-this-can-move-the-robot",
        action="store_true",
        help="Required together with --publish.",
    )

    args = parser.parse_args()
    packet_path = Path(args.packet)

    try:
        packet = load_packet(packet_path)
        validate_packet(packet)
        print_preview(packet)

        if not args.publish:
            print("Not publishing because --publish was not provided.")
            return 0

        if not args.i_understand_this_can_move_the_robot:
            print(
                "Refusing to publish: missing "
                "--i-understand-this-can-move-the-robot"
            )
            return 2

        if not packet_allows_robot_motion(packet):
            print(
                "Refusing to publish: packet safety flags do not allow robot motion.\n"
                "Required: safety.publish_to_robot=true and safety.dry_run_only=false"
            )
            return 3

        publish_ros1(packet)
        print("Published one JointTrajectory command.")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
