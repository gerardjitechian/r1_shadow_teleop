# Shadow ROS1 Sender Safety Notes

Current status:
- `tools/shadow_ros1_sender.py` can read a generated Shadow command packet.
- It validates the expected right Shadow Hand Lite joint order.
- It prints the `JointTrajectory` command that would be sent.
- By default, it does not publish.

Current safety gates:
- `--publish` is required.
- `--i-understand-this-can-move-the-robot` is required.
- The packet must contain:
  - `safety.publish_to_robot: true`
  - `safety.dry_run_only: false`

The current R1-generated packets intentionally contain:
- `safety.publish_to_robot: false`
- `safety.dry_run_only: true`

Therefore, current packets are refused by the ROS1 sender even when `--publish` is passed.

Before any real Shadow Hand command:
- Confirm emergency stop procedure.
- Confirm controller state and joint limits.
- Use a simulator if available.
- Use slow trajectories.
- Clamp all joint values.
- Start with a known safe open-hand command.
