# Current Status — 2026-05-22 End-of-Lab Snapshot

## Table of Contents

- [Summary](#summary)
- [Current Repository State](#current-repository-state)
- [R1 Machine Status](#r1-machine-status)
- [SenseGlove R1 Status](#senseglove-r1-status)
- [Two-Glove Issue](#two-glove-issue)
- [Shadow Hand Status](#shadow-hand-status)
- [Current Mapping Status](#current-mapping-status)
- [Current Command Packet Status](#current-command-packet-status)
- [Files and Artifacts](#files-and-artifacts)
- [What To Do First Next Time](#what-to-do-first-next-time)
- [Shutdown Notes](#shutdown-notes)

---

## Summary

As of the end of the 2026-05-22 lab session, the project has a working **R1-side dry-run teleoperation pipeline**:

```text
Right SenseGlove R1
        ↓
/r1/glove69/rh/glove_states
        ↓
R1 ROS 2 listener
        ↓
calibrated thumb/index/ring flexion
        ↓
Shadow Hand Lite 12-joint target preview
        ↓
JointTrajectory preview
        ↓
dry-run JSON command packet
        ↓
print-only Shadow-side validator/sender
```

The project does **not** yet move the physical Shadow Hand.

---

## Current Repository State

Repository path on R1 Ubuntu machine:

```text
~/r1_ws/src/r1_shadow_teleop
```

Expected Git state before shutting down:

```bash
cd ~/r1_ws/src/r1_shadow_teleop
git status
```

Desired output:

```text
nothing to commit, working tree clean
```

Recent implemented milestones:

- R1 glove listener.
- R1 pose calibration recorder.
- R1 calibration constants and calibrated flexion mapping.
- Shadow mapping layer.
- Shadow `JointTrajectory` preview.
- Dry-run JSON command packet.
- Print-only Shadow command receiver.
- Guarded ROS 1 Shadow sender skeleton.
- Shadow print-only transfer bundle script.

---

## R1 Machine Status

Machine:

```text
robotlabserver
```

Environment:

```text
Ubuntu 24.04.4 LTS
ROS 2 Jazzy
Python 3.12.3
Workspace: ~/r1_ws
Virtual environment: ~/r1_ws/.venv
```

Activation:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
```

The activation script should report:

```text
R1 environment active
ROS_DISTRO=jazzy
VIRTUAL_ENV=/home/gerard/r1_ws/.venv
```

---

## SenseGlove R1 Status

Known devices:

| Device | Glove ID | Hand | Topic when working alone |
|---|---:|---|---|
| Right R1 | 69 | Right | `/r1/glove69/rh/glove_states` |
| Left R1 | 67 | Left | `/r1/glove67/lh/glove_states` |

Current development target:

```text
Right glove only
/r1/glove69/rh/glove_states
```

Right-glove launch:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 launch r1_bringup r1.launch.py
```

Expected:

- R1 GUI opens.
- Right hand skeleton moves in the GUI.
- Topic `/r1/glove69/rh/glove_states` publishes.

---

## Two-Glove Issue

The two-glove issue is not solved.

Observed facts:

- Linux sees both gloves over USB.
- Both gloves show the same USB vendor/product ID:
  - `2e8a:10f3 SenseGlove R1`
- Each glove works individually through ROS.
- USB permissions were open/read-write.
- Two-glove launch starts `r1_manager` but no glove topics are created.
- Direct Python API test with `SG_main.init(2, REAL_GLOVE_USB)` detects only one glove and waits indefinitely for the second.

Current interpretation:

```text
The issue appears below the ROS layer in the SenseGlove API/SDK multi-device initialization path.
```

Current workaround:

```text
Use right glove only for teleoperation development.
```

Support packet:

```text
~/r1_support_clean_20260522_v3.tar.gz
```

---

## Shadow Hand Status

Shadow environment discovered:

```text
Host laptop: Ubuntu 20.04.4 LTS
ROS: ROS 1 Noetic inside Docker
Container: dexterous_hand_real_hw
Image: public.ecr.aws/shadowrobot/dexterous-hand:noetic-release
Network mode: host
```

Discovered command topic:

```text
/rh_trajectory_controller/command
```

Discovered state topics include:

```text
/joint_states
/rh_trajectory_controller/state
/rh/tactile
/rh/palm_extras
```

Discovered active joint set:

```text
rh_FFJ1
rh_FFJ2
rh_FFJ3
rh_FFJ4
rh_RFJ1
rh_RFJ2
rh_RFJ3
rh_RFJ4
rh_THJ1
rh_THJ2
rh_THJ4
rh_THJ5
```

MoveIt group discovered:

```text
right_hand
```

Finger groups observed:

```text
rh_thumb
rh_first_finger
rh_ring_finger
```

---

## Current Mapping Status

Current selected mapping:

| R1 finger | Shadow group | Shadow joints |
|---|---|---|
| Thumb | Thumb | `rh_THJ*` |
| Index | First finger | `rh_FFJ*` |
| Ring | Ring finger | `rh_RFJ*` |

Ignored for now:

```text
R1 middle
R1 pinky
```

Reason:

```text
The R1 glove has 5 fingers, while the discovered Shadow Hand Lite configuration has 3 active groups for this project: thumb, first finger, and ring finger.
```

---

## Current Command Packet Status

The R1-side listener generates:

```text
runtime_data/shadow_hand/latest_command_packet.json
```

Example safety flags:

```json
{
  "dry_run_only": true,
  "publish_to_robot": false
}
```

This file is generated and should not be committed.

The command packet includes:

- packet type
- source identifier
- creation timestamp
- safety flags
- ordered Shadow joint names
- 12 positions
- command duration

Current expected duration:

```text
2.0 seconds
```

---

## Files and Artifacts

### Important repository files

```text
README.md
docs/current_status_2026-05-22.md
docs/runbook_r1_machine.md
docs/shadow_handoff_runbook.md
docs/roadmap.md
docs/safety_notes.md
```

### Important generated local files

```text
runtime_data/shadow_hand/latest_command_packet.json
```

Do not commit this generated packet.

### Important calibration/data files

```text
docs/calibrations/r1_right_glove_calibration_latest.csv
docs/r1_glove_state_interface.txt
docs/r1_glove69_raw_echo_5sec.txt
```

### Important transfer bundle

```text
~/shadow_print_only_bundle_<timestamp>.tar.gz
```

This should be copied to USB or transferred to the Shadow laptop. It should not be committed.

---

## What To Do First Next Time

Recommended first actions next session:

1. On the R1 machine, verify repo status:

   ```bash
   cd ~/r1_ws/src/r1_shadow_teleop
   git pull
   git status
   ```

2. On the Shadow laptop, copy the print-only bundle from USB.

3. Run the print-only Shadow-side test outside Docker.

4. Run the print-only Shadow-side test inside Docker.

5. Confirm that the script refuses to publish.

6. After print-only tests pass, implement the live UDP sender/receiver, still print-only.

---

## Shutdown Notes

Before shutting down the R1 machine:

1. Stop all ROS terminals with `Ctrl+C`.
2. Confirm Git is clean:

   ```bash
   cd ~/r1_ws/src/r1_shadow_teleop
   git status
   ```

3. Push any final documentation changes:

   ```bash
   git add README.md docs/*.md
   git commit -m "Add project documentation and shutdown notes"
   git push
   ```

4. Shut down Ubuntu normally.

Shadow laptop shutdown:

1. Close RViz and Shadow apps.
2. Stop demos if any are running.
3. Shut down the Shadow laptop normally.
4. Shut down the NUC normally if applicable.
5. Disconnect power to the hand only after software is stopped.
