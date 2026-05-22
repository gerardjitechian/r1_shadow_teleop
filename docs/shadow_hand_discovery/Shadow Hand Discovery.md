# Shadow Hand Discovery - 2026-05-22

## System

- Host laptop: Ubuntu 20.04.4 LTS
- ROS: ROS 1 Noetic
- Docker container: `dexterous_hand_real_hw`
- Docker image: `public.ecr.aws/shadowrobot/dexterous-hand:noetic-release`
- Container status: running
- Network mode: host
- NUC/control computer reachable on Shadow network

## Hand configuration

The discovered hand appears to be a right Shadow Dexterous Hand Lite / reduced right-hand configuration.

Detected joints:

- `rh_FFJ1`
- `rh_FFJ2`
- `rh_FFJ3`
- `rh_FFJ4`
- `rh_RFJ1`
- `rh_RFJ2`
- `rh_RFJ3`
- `rh_RFJ4`
- `rh_THJ1`
- `rh_THJ2`
- `rh_THJ4`
- `rh_THJ5`

MoveIt group:

- `right_hand`

Finger groups observed:

- `rh_thumb`
- `rh_first_finger`
- `rh_ring_finger`

## State topics

- `/joint_states`
  - Type: `sensor_msgs/JointState`
  - Published by: `/sr_hand_robot`

- `/rh_trajectory_controller/state`
  - Type: `control_msgs/JointTrajectoryControllerState`
  - Published by: `/sr_hand_robot`

- `/rh/tactile`
  - Type: `sr_robot_msgs/ShadowPST`
  - Published by: `/sr_hand_robot`

- `/rh/palm_extras`
  - Type: `std_msgs/Float64MultiArray`
  - Published by: `/sr_hand_robot`

## Command topics

Primary candidate command topic:

- `/rh_trajectory_controller/command`
  - Type: `trajectory_msgs/JointTrajectory`
  - Subscribed by: `/sr_hand_robot`

Individual joint command topics also exist:

- `/sh_rh_ffj0_position_controller/command`
- `/sh_rh_ffj3_position_controller/command`
- `/sh_rh_ffj4_position_controller/command`
- `/sh_rh_rfj0_position_controller/command`
- `/sh_rh_rfj3_position_controller/command`
- `/sh_rh_rfj4_position_controller/command`
- `/sh_rh_thj1_position_controller/command`
- `/sh_rh_thj2_position_controller/command`
- `/sh_rh_thj4_position_controller/command`
- `/sh_rh_thj5_position_controller/command`

All listed individual command topics use:

- `std_msgs/Float64`

## Integration implications

The R1 SenseGlove stack is ROS 2. The Shadow Hand stack is ROS 1 Noetic in Docker.

Likely integration approaches:

1. Use a ROS 1 ↔ ROS 2 bridge.
2. Build a ROS 1 Shadow-side wrapper and communicate with the ROS 2 R1-side app over a simple network protocol.
3. Keep the first prototype one-way:
   - R1 glove state → mapping node → Shadow hand trajectory command.

Initial command target should probably be:

- `/rh_trajectory_controller/command`

Safety requirements before commanding hardware:

- Start read-only.
- Test in simulation if available.
- Clamp all joint commands to known safe ranges.
- Use slow movement durations.
- Add a deadman/enable switch.
- Confirm emergency stop procedure.
