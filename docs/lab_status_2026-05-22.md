# Lab Status - 2026-05-22

## Environment

- Ubuntu 24.04.4 LTS
- ROS 2 Jazzy
- SenseGlove R1 ROS workspace: `~/r1_ws`
- R1 ROS wrapper: `~/r1_ws/src/rembrandt_ros`
- R1 Python API: `~/r1_ws/src/rembrandt-api`
- Project repo: `~/r1_ws/src/r1_shadow_teleop`

## Working

- R1 ROS workspace builds successfully.
- R1 simulator works.
- Left glove works individually.
  - Topic: `/r1/glove67/lh/glove_states`
  - Force command topic: `/r1/glove67/lh/force_commands`
- Right glove works individually.
  - Topic: `/r1/glove69/rh/glove_states`
  - Force command topic: `/r1/glove69/rh/force_commands`
- Both gloves are visible to Ubuntu over USB simultaneously.

## Known issue

Two-glove live mode does not currently work.

Command:

```bash
ros2 launch r1_bringup r1.launch.py num_gloves:=2

Result:

r1_manager starts.
No glove state topics are created.
Direct API test shows SG_main.init(2, REAL_GLOVE_USB) detects only glove 69 and waits for the second glove indefinitely.

Support packet created:

~/r1_support_clean_20260522_v3.tar.gz
Next development target

Start with one-glove research code:

Subscribe to /r1/glove67/lh/glove_states or /r1/glove69/rh/glove_states.
Convert raw R1GloveState messages into an internal HandFrame representation.
Log normalized finger values and fingertip distances.
Later map these values to Shadow Hand command topics.
