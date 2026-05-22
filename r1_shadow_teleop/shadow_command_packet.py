import json
from datetime import datetime, timezone
from pathlib import Path

from trajectory_msgs.msg import JointTrajectory


def trajectory_to_packet(msg: JointTrajectory, source: str = "r1_glove69_rh") -> dict:
    """
    Convert a JointTrajectory preview into a simple JSON-serializable packet.

    This is for dry-run bridge development only.
    It does NOT publish to the Shadow Hand.
    """

    if msg.points:
        point = msg.points[0]
        positions = [float(x) for x in point.positions]
        duration_sec = (
            float(point.time_from_start.sec)
            + float(point.time_from_start.nanosec) / 1_000_000_000.0
        )
    else:
        positions = []
        duration_sec = 0.0

    return {
        "type": "shadow_joint_trajectory_preview",
        "source": source,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "publish_to_robot": False,
            "dry_run_only": True,
        },
        "trajectory": {
            "joint_names": list(msg.joint_names),
            "positions": positions,
            "duration_sec": duration_sec,
        },
    }


def format_packet(packet: dict) -> str:
    return json.dumps(packet, indent=2, sort_keys=True)


def save_packet(packet: dict, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_packet(packet) + "\n")
