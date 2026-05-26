# Current Roadmap

## Current Status

The application is still **dry-run only**. It reads the SenseGlove R1 ROS 2 topic, applies active calibration, shows listener diagnostics, builds a placeholder Shadow Hand preview, and writes a safety-marked dry-run packet. It does not publish to the physical Shadow Hand.

Current pipeline facts:

- `input_source`: `senseglove_r1` only
- default config: right SenseGlove R1 input to right `hand_lite_3finger` Shadow Hand preview
- mapping profile: `hand_lite_3finger_placeholder`
- mapped source: calibrated flexion only
- abduction: listener diagnostics only, not used for Shadow mapping
- filtering: `pass_through` only
- packet path: `runtime_data/shadow_hand/latest_command_packet.json`
- generated calibration path: `runtime_data/senseglove_r1/calibrations/`

## Next Milestone

The next practical milestone is Shadow Hand model/config expansion plus real Shadow-side discovery. The goal is to replace placeholder assumptions with verified facts about the actual hand, controller, joint order, and safe ranges while remaining dry-run-only.

Do this before UDP/TCP transport, ROS bridge work, filtering/smoothing logic, PID, abduction-to-Shadow mapping, or live publishing.

## Next Implementation Areas

1. Shadow Hand model metadata
   - Make the current `hand_lite_3finger` model explicit: active digits, expected joints, joint groups, and preview mapping support.
   - Keep `hand_full_5finger` as a future supported model shape without pretending it is mapped.

2. Shadow-side discovery
   - Collect evidence from the real ROS 1/Docker Shadow setup: topics, controller params, `/joint_states`, robot description, active joints, and command topic shape.
   - Confirm whether `/rh_trajectory_controller/command` is the right target and whether partial trajectories are accepted.

3. Mapping profiles and validation
   - Move from placeholder flexion scaling to model-driven mapping profiles.
   - Validate joint order, joint limits, direction/sign conventions, neutral pose, safe open pose, and safe per-joint ranges before any physical motion.

4. Dry-run safety validation
   - Add checks for stale packets, missing joints, wrong joint order, out-of-range targets, sudden jumps, and unsafe defaults.
   - Keep packets dry-run-only until these checks are proven.

5. Later pipeline work
   - Turn the current `pass_through` filter stage into real deadbands, rate limits, smoothing, and sudden-jump prevention after mapping is validated.
   - Design transport/bridge later: UDP/TCP/custom packets, ROS 1/ROS 2 bridge, or a wrapper process.
   - Add guarded live publishing only after dry-run validation, operator enable/deadman design, stale-packet handling, safe fallback behavior, and emergency stop procedures exist.

## When Returning

From `~/r1_ws`:

```bash
source ~/r1_ws/activate_r1.sh
colcon build --symlink-install --packages-select r1_shadow_teleop
source install/setup.bash
```

If calibration data is stale or missing, run:

```bash
ros2 run r1_shadow_teleop senseglove_r1_calibration
```

Run the listener with the Shadow preview visible:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener --ros-args -p show_shadow_targets:=true
```

Expected listener truth labels:

```text
mapping_profile: hand_lite_3finger_placeholder
mapped_from: calibrated_flexion
abduction_used_for_shadow_mapping: false
filter_profile: pass_through
safety: dry-run only, not publishing to Shadow
```

Before planning live control, collect Shadow-side ROS evidence from the Shadow laptop/container. Useful commands may include:

```bash
rostopic list
rostopic info /rh_trajectory_controller/command
rostopic echo -n 1 /joint_states
rosparam get /rh_trajectory_controller
rosparam get /robot_description
rosservice list
```

## Archived Planning

The staged Phase 1-7 refactor plan has been archived at `docs/archive/refactor_plan_phases_1_7.md`. Older files under `docs/archive/` are historical and may use old command names, old paths, or outdated phase numbering.
