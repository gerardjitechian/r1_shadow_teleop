# R1 Machine Runbook

## Table of Contents

- [Purpose](#purpose)
- [Machine and Repository](#machine-and-repository)
- [Start-of-Session Checklist](#start-of-session-checklist)
- [Activate the R1 Environment](#activate-the-r1-environment)
- [Launch the Right R1 Glove](#launch-the-right-r1-glove)
- [Run the Calibrated Dry-Run Listener](#run-the-calibrated-dry-run-listener)
- [Run the Calibration Printer](#run-the-calibration-printer)
- [Run the Calibration Utility](#run-the-calibration-utility)
- [Generate a Shadow Print-Only Bundle](#generate-a-shadow-print-only-bundle)
- [Test the Shadow Packet Locally](#test-the-shadow-packet-locally)
- [Git Workflow](#git-workflow)
- [Common Problems](#common-problems)
- [End-of-Session Shutdown](#end-of-session-shutdown)

---

## Purpose

This runbook is for working on the R1 Ubuntu machine:

```text
robotlabserver
```

It covers:

- starting the SenseGlove R1 ROS 2 stack
- running the dry-run teleoperation preview
- generating calibration data
- generating a Shadow-side print-only transfer bundle
- committing and pushing changes safely

---

## Machine and Repository

Workspace:

```text
~/r1_ws
```

Repository:

```text
~/r1_ws/src/r1_shadow_teleop
```

Right R1 glove topic:

```text
/r1/glove69/rh/glove_states
```

Primary development assumption:

```text
Use the right R1 glove only.
```

---

## Start-of-Session Checklist

Run:

```bash
cd ~/r1_ws/src/r1_shadow_teleop
git pull
git status
```

Expected:

```text
nothing to commit, working tree clean
```

If there are uncommitted changes, inspect them before starting new work:

```bash
git diff
git status
```

---

## Activate the R1 Environment

Every new terminal:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
```

Expected:

```text
R1 environment active
ROS_DISTRO=jazzy
VIRTUAL_ENV=/home/gerard/r1_ws/.venv
```

If ROS commands fail, re-run the activation script.

---

## Launch the Right R1 Glove

Terminal 1:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 launch r1_bringup r1.launch.py
```

Expected:

- GUI opens.
- Hand skeleton appears.
- Right glove motion appears in the GUI.

Check topics if needed:

```bash
ros2 topic list | grep glove
```

Expected topic:

```text
/r1/glove69/rh/glove_states
```

---

## Run the Calibrated Dry-Run Listener

Terminal 2:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop senseglove_r1_listener
```

Expected output is a dry-run dashboard with calibration reporting and an R1 finger table. The calibration section should include the active resolver, source files or registry components, status, and any recalibration warnings. The table includes raw flexion, calibrated flexion, raw/sdk abduction, neutral baseline, signed abduction offset, reliable spread when available, and abduction status.

This node writes:

```text
~/r1_ws/src/r1_shadow_teleop/runtime_data/shadow_hand/latest_command_packet.json
```

This is a generated file and should not be committed.

---

## Run the Calibration Printer

Use this when you want a compact live view of the R1 values.

Terminal 2:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop senseglove_r1_calibration_printer
```

Expected output format:

```text
flex T=... I=... M=... R=... P=... | abd T=... I=... M=... R=... P=...
```

This is mainly for quick debugging.

---

## Run the Calibration Utility

Use this when recalibrating the glove. The default command is interactive and guided.

Terminal 2:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop senseglove_r1_calibration
```

For each pose, the utility shows a separated step panel with explicit, comfort-focused instructions, waits for Enter, shows settle/sample progress based on `settle_seconds` and `sample_seconds`, then asks what to do next:

```text
Enter/a = accept and continue
r       = repeat this pose if the capture looked bad
s       = skip optional pose
q       = abort safely
```

Complete calibrations write timestamped CSV/JSON files and update latest copies in the package-local calibration directory:

```text
runtime_data/senseglove_r1/calibrations/r1_right_glove_calibration_<timestamp>.csv
runtime_data/senseglove_r1/calibrations/r1_right_glove_calibration_latest.csv
```

New calibration runs write to `runtime_data/senseglove_r1/calibrations/` by default. Generated CSV/JSON/registry files are ignored by Git, and each saved run updates the package-local registry:

```text
runtime_data/senseglove_r1/calibrations/calibration_registry.json
```

Incomplete or aborted runs are saved with incomplete metadata when useful, but latest is not updated.

Longer timing example:

```bash
ros2 run r1_shadow_teleop senseglove_r1_calibration --ros-args -p settle_seconds:=1.5 -p sample_seconds:=4.0
```

Non-interactive setup examples:

```bash
ros2 run r1_shadow_teleop senseglove_r1_calibration --ros-args -p calibration_mode:=abduction -p fingers:=all -p hand:=right -p non_interactive:=true
ros2 run r1_shadow_teleop senseglove_r1_calibration --ros-args -p calibration_mode:=flexion -p fingers:=index -p hand:=right -p non_interactive:=true
ros2 run r1_shadow_teleop senseglove_r1_calibration --ros-args -p calibration_mode:=both -p fingers:=all -p hand:=right -p non_interactive:=true
ros2 run r1_shadow_teleop senseglove_r1_calibration --ros-args -p calibration_mode:=pinch_validation -p fingers:=index,middle,ring,pinky -p hand:=right -p non_interactive:=true
```

Run the listener with the default active calibration. The default resolver is `composed_latest`, which chooses the newest valid record per hand, dimension, and finger so a flexion-only run does not erase previous abduction calibration:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener
```

The listener reports the active dry-run teleop config. Phase 6 supports these defaults: `input_source:=senseglove_r1`, `input_hand:=right`, `target_hand:=right`, `shadow_hand_model:=hand_lite_3finger`, and `mirror_mode:=none`. `hand_full_5finger` is recognized as future metadata only; the current preview mapping remains the existing Hand Lite-style dry-run mapping. The listener should also report `mapping_profile: hand_lite_3finger_placeholder`, `mapped_from: calibrated_flexion`, `abduction_used_for_shadow_mapping: false`, and `filter_profile: pass_through`.

Resolver modes:

```text
composed_latest  newest valid record per dimension/finger, default
latest_complete  newest single run with complete flexion and abduction
explicit_file    only the file passed with calibration_csv_path
```

Example:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener --ros-args -p calibration_resolver_mode:=latest_complete
```

Run the listener with a specific calibration file. Explicit paths still override the registry resolver and use only that CSV plus its sidecar:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener --ros-args -p calibration_csv_path:=runtime_data/senseglove_r1/calibrations/r1_right_glove_calibration_YYYY-MM-DD_HHMMSS.csv
```

Run the listener in plain/no-color mode:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener --ros-args -p use_rich:=false -p color_output:=false
```

Abduction note: raw/sdk abduction is directional SDK data. The listener also shows the calibration neutral baseline, signed offset from neutral, spread, and an abduction status. Spread is shown only when schema v2 calibration metadata is reliable; missing quality metadata or warnings mean recalibration is recommended.

Return checklist:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener --ros-args -p show_shadow_targets:=true
```

Confirm the listener shows:

```text
mapping_profile: hand_lite_3finger_placeholder
mapped_from: calibrated_flexion
abduction_used_for_shadow_mapping: false
filter_profile: pass_through
safety: dry-run only, not publishing to Shadow
```

The dry-run packet should be written to `runtime_data/shadow_hand/latest_command_packet.json`. Do not treat this as live publishing.

---

## Generate a Shadow Print-Only Bundle

Make sure `senseglove_r1_listener` has already generated:

```text
runtime_data/shadow_hand/latest_command_packet.json
```

Then run:

```bash
cd ~/r1_ws/src/r1_shadow_teleop
tools/make_shadow_print_bundle.sh
```

Expected output:

```text
Created:
/home/gerard/shadow_print_only_bundle_<timestamp>.tar.gz
```

Find bundles:

```bash
ls -lh ~/shadow_print_only_bundle_*.tar.gz
```

Copy the newest `.tar.gz` to USB or transfer it to the Shadow laptop.

---

## Test the Shadow Packet Locally

From the R1 repo, after the listener has generated a packet:

```bash
cd ~/r1_ws/src/r1_shadow_teleop

python3 tools/shadow_ros1_sender.py   --packet runtime_data/shadow_hand/latest_command_packet.json
```

Expected:

```text
Not publishing because --publish was not provided.
```

Safety refusal test:

```bash
python3 tools/shadow_ros1_sender.py   --packet runtime_data/shadow_hand/latest_command_packet.json   --publish   --i-understand-this-can-move-the-robot
```

Expected:

```text
Refusing to publish: packet safety flags do not allow robot motion.
Required: safety.publish_to_robot=true and safety.dry_run_only=false
```

This refusal is success.

---

## Git Workflow

Check status:

```bash
cd ~/r1_ws/src/r1_shadow_teleop
git status
```

Add intentional code/doc changes:

```bash
git add <files>
git commit -m "Short descriptive message"
git push
```

Do not commit generated runtime packet:

```text
runtime_data/shadow_hand/latest_command_packet.json
```

Commit documentation:

```bash
git add README.md docs/*.md
git commit -m "Add project documentation and shutdown notes"
git push
```

Final check:

```bash
git status
```

Desired:

```text
nothing to commit, working tree clean
```

---

## Common Problems

### GUI moves, but listener prints zeros

Likely parsing the wrong field or handling ROS array fields incorrectly. Confirm:

```bash
ros2 interface show r1_msgs/msg/R1GloveState
```

The useful field should be:

```text
normalized_finger_positions
```

### Listener receives messages, but values seem offset

That is expected. Use calibration. Open hand is not necessarily zero. Current code uses open/closed baselines.

### `runtime_data/shadow_hand/latest_command_packet.json` appears in Git status

It should be ignored. Confirm `.gitignore` contains:

```text
runtime_data/shadow_hand/*
!runtime_data/shadow_hand/.gitkeep
```

### Two-glove mode does not publish topics

Known unresolved issue. Use right glove only.

---

## End-of-Session Shutdown

1. Stop ROS processes with `Ctrl+C`.
2. Confirm Git status:

   ```bash
   cd ~/r1_ws/src/r1_shadow_teleop
   git status
   ```

3. Commit/push intentional changes.
4. Confirm clean tree.
5. Shut down Ubuntu normally.
