# R1 Machine Runbook

## Table of Contents

- [Purpose](#purpose)
- [Machine and Repository](#machine-and-repository)
- [Start-of-Session Checklist](#start-of-session-checklist)
- [Activate the R1 Environment](#activate-the-r1-environment)
- [Launch the Right R1 Glove](#launch-the-right-r1-glove)
- [Run the Calibrated Dry-Run Listener](#run-the-calibrated-dry-run-listener)
- [Run the Calibration Printer](#run-the-calibration-printer)
- [Run the Pose Recorder](#run-the-pose-recorder)
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
ros2 run r1_shadow_teleop r1_glove_listener
```

Expected output:

```text
R1 → Shadow calibrated dry-run mapping
Raw R1 flexion, scaled 0.0..1.0
Calibrated R1 flexion, open≈0.0 closed≈1.0
Human-readable Shadow preview
Shadow JointTrajectory preview, NOT publishing
Saved latest dry-run command packet to:
  docs/latest_shadow_command_packet.json
```

This node writes:

```text
~/r1_ws/src/r1_shadow_teleop/docs/latest_shadow_command_packet.json
```

This is a generated file and should not be committed.

---

## Run the Calibration Printer

Use this when you want a compact live view of the R1 values.

Terminal 2:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop r1_calibration_printer
```

Expected output format:

```text
flex T=... I=... M=... R=... P=... | abd T=... I=... M=... R=... P=...
```

This is mainly for quick debugging.

---

## Run the Pose Recorder

Use this when recalibrating the glove.

Terminal 2:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop r1_pose_recorder
```

It will prompt for poses one at a time.

Pose descriptions:

```text
open_relaxed
- Hand open and relaxed.
- Fingers naturally extended.
- Thumb relaxed/open.

full_fist
- Close all fingers into a fist.
- Thumb can naturally rest where comfortable.

thumb_only
- Keep index/middle/ring/pinky open.
- Bend only the thumb inward toward the palm.
- Do not pinch.

index_only
- Keep thumb/middle/ring/pinky open.
- Bend only the index finger.

middle_only
- Keep other fingers as open as possible.
- Bend only the middle finger.

ring_only
- Keep other fingers as open as possible.
- Bend only the ring finger.

pinky_only
- Keep other fingers as open as possible.
- Bend only the pinky.

index_thumb_pinch
- Touch thumb tip to index fingertip.
- Keep other fingers as open as possible.

ring_thumb_pinch
- Touch thumb tip to ring fingertip.
- Approximate is fine.
```

Output file:

```text
~/r1_ws/src/r1_shadow_teleop/docs/r1_right_glove_pose_calibration.csv
```

If you intentionally update calibration data, commit the CSV.

---

## Generate a Shadow Print-Only Bundle

Make sure `r1_glove_listener` has already generated:

```text
docs/latest_shadow_command_packet.json
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

python3 tools/shadow_ros1_sender.py   --packet docs/latest_shadow_command_packet.json
```

Expected:

```text
Not publishing because --publish was not provided.
```

Safety refusal test:

```bash
python3 tools/shadow_ros1_sender.py   --packet docs/latest_shadow_command_packet.json   --publish   --i-understand-this-can-move-the-robot
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
docs/latest_shadow_command_packet.json
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

### `docs/latest_shadow_command_packet.json` appears in Git status

It should be ignored. Confirm `.gitignore` contains:

```text
docs/latest_shadow_command_packet.json
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
