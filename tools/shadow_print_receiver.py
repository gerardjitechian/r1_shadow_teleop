#!/usr/bin/env python3

import argparse
import hashlib
import json
import sys
import time
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

    safety = packet.get("safety", {})
    if safety.get("publish_to_robot") is not False:
        raise ValueError("Refusing packet because publish_to_robot is not false")

    if safety.get("dry_run_only") is not True:
        raise ValueError("Refusing packet because dry_run_only is not true")

    trajectory = packet.get("trajectory", {})
    joint_names = trajectory.get("joint_names", [])
    positions = trajectory.get("positions", [])

    if joint_names != EXPECTED_SHADOW_JOINT_NAMES:
        raise ValueError(
            "Joint names do not match expected Shadow Hand Lite joint order.\n"
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


def packet_fingerprint(packet: dict) -> str:
    stable = {
        "joint_names": packet["trajectory"]["joint_names"],
        "positions": packet["trajectory"]["positions"],
        "duration_sec": packet["trajectory"]["duration_sec"],
    }

    raw = json.dumps(stable, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def print_preview(packet: dict) -> None:
    trajectory = packet["trajectory"]
    joint_names = trajectory["joint_names"]
    positions = trajectory["positions"]
    duration_sec = trajectory["duration_sec"]

    print()
    print("Shadow-side print receiver")
    print("==========================")
    print(f"Source packet time: {packet.get('created_utc')}")
    print(f"Would publish to:   {COMMAND_TOPIC}")
    print("Publish status:     DISABLED / PRINT ONLY")
    print()
    print("ROS1 JointTrajectory preview:")
    print("  joint_names:")

    for name in joint_names:
        print(f"    - {name}")

    print("  points[0].positions:")

    for name, pos in zip(joint_names, positions):
        print(f"    {name}: {float(pos): .3f}")

    print(f"  points[0].time_from_start: {float(duration_sec):.3f} sec")
    print()
    print("Human-readable grouping:")
    print(
        "  Shadow first finger / rh_FFJ*: "
        f"{positions[0]:.3f}, {positions[1]:.3f}, {positions[2]:.3f}, {positions[3]:.3f}"
    )
    print(
        "  Shadow ring finger  / rh_RFJ*: "
        f"{positions[4]:.3f}, {positions[5]:.3f}, {positions[6]:.3f}, {positions[7]:.3f}"
    )
    print(
        "  Shadow thumb        / rh_THJ*: "
        f"{positions[8]:.3f}, {positions[9]:.3f}, {positions[10]:.3f}, {positions[11]:.3f}"
    )
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Read an R1-generated Shadow command packet and print the ROS1 command preview only."
    )

    parser.add_argument(
        "--packet",
        default="runtime_data/shadow_hand/latest_command_packet.json",
        help="Path to latest_command_packet.json",
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep watching the packet file and print when the command changes",
    )

    parser.add_argument(
        "--period",
        type=float,
        default=1.0,
        help="Watch period in seconds",
    )

    args = parser.parse_args()
    path = Path(args.packet)

    last_fingerprint = None

    while True:
        try:
            packet = load_packet(path)
            validate_packet(packet)

            current_fingerprint = packet_fingerprint(packet)

            if current_fingerprint != last_fingerprint:
                print_preview(packet)
                last_fingerprint = current_fingerprint

        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)

        if not args.watch:
            break

        time.sleep(args.period)


if __name__ == "__main__":
    main()
