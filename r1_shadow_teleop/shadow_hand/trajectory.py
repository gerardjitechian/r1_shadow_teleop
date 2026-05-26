from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

from r1_shadow_teleop.shadow_hand.mapping_preview import ShadowTarget


def build_shadow_joint_trajectory(
    target: ShadowTarget,
    duration_sec: float = 2.0,
) -> JointTrajectory:
    """
    Build the expected Shadow JointTrajectory message shape.

    This function only builds the message. It does NOT publish it.
    """
    msg = JointTrajectory()
    msg.joint_names = list(target.joint_names)

    point = JointTrajectoryPoint()
    point.positions = [float(x) for x in target.positions]

    sec = int(duration_sec)
    nanosec = int((duration_sec - sec) * 1_000_000_000)
    point.time_from_start = Duration(sec=sec, nanosec=nanosec)

    msg.points.append(point)
    return msg


def format_joint_trajectory(msg: JointTrajectory) -> str:
    lines = [
        "Shadow JointTrajectory preview, NOT publishing:",
        f"  joint_names: {list(msg.joint_names)}",
        "  point[0].positions:",
    ]

    if not msg.points:
        lines.append("    <no points>")
        return "\n".join(lines)

    point = msg.points[0]

    for name, pos in zip(msg.joint_names, point.positions):
        lines.append(f"    {name}: {pos: .3f}")

    lines.append(
        f"  time_from_start: {point.time_from_start.sec}."
        f"{point.time_from_start.nanosec:09d} sec"
    )

    return "\n".join(lines)
