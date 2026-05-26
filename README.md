# R1 Shadow Teleop

> SenseGlove R1 → ROS 2 → calibrated 3-finger mapping → Shadow Hand Lite command preview.

**Current status as of 2026-05-22, end of lab session:** this repository can read the right SenseGlove R1, parse calibrated thumb/index/ring motion, map those values into the discovered right Shadow Hand Lite joint set, build a Shadow-style `JointTrajectory` preview, save a dry-run JSON command packet, and validate/print that packet on the Shadow side. It does **not** yet publish commands to the physical Shadow Hand.

---

## Table of Contents

- [Project Goal](#project-goal)
- [Current Safety Status](#current-safety-status)
- [System Overview](#system-overview)
- [What Works Today](#what-works-today)
- [What Does Not Work Yet](#what-does-not-work-yet)
- [Hardware and Software Setup](#hardware-and-software-setup)
- [Current Finger Mapping](#current-finger-mapping)
- [Current Data Pipeline](#current-data-pipeline)
- [Repository Layout](#repository-layout)
- [Important Code Modules](#important-code-modules)
- [Quick Start: R1 Machine](#quick-start-r1-machine)
- [Quick Start: Shadow Print-Only Bundle](#quick-start-shadow-print-only-bundle)
- [Calibration Summary](#calibration-summary)
- [Generated Files](#generated-files)
- [Known Issues and Open Questions](#known-issues-and-open-questions)
- [Next Steps](#next-steps)
- [References](#references)

---

## Project Goal

The near-term goal is **one-way teleoperation**:

```text
SenseGlove R1 right glove
        ↓
ROS 2 R1 topic
        ↓
R1 parser + calibration
        ↓
thumb/index/ring mapping
        ↓
Shadow Hand Lite joint target generation
        ↓
network bridge
        ↓
ROS 1 Shadow-side receiver
        ↓
/rh_trajectory_controller/command
        ↓
Shadow Hand moves
```

Force feedback is **not** part of the current implementation phase. The initial goal is motion-only teleoperation: moving the SenseGlove should eventually move the physical Shadow Hand in near real time.

---

## Current Safety Status

**The current code is dry-run only.**

The repository currently generates command previews and safety-marked packets. Current packets include:

```json
{
  "safety": {
    "dry_run_only": true,
    "publish_to_robot": false
  }
}
```

The ROS 1 sender skeleton refuses to publish unless all of the following are true:

1. The user passes `--publish`.
2. The user passes `--i-understand-this-can-move-the-robot`.
3. The packet has `safety.publish_to_robot: true`.
4. The packet has `safety.dry_run_only: false`.

The current R1-generated packets intentionally do **not** satisfy those publishing conditions.

Do **not** bypass those gates until the Shadow Hand safety checklist has been completed.

---

## System Overview

### R1 side

- Machine: `robotlabserver`
- OS: Ubuntu 24.04.4 LTS
- ROS: ROS 2 Jazzy
- Workspace: `~/r1_ws`
- Repository: `~/r1_ws/src/r1_shadow_teleop`
- Right glove:
  - Device/glove ID: `69`
  - ROS topic: `/r1/glove69/rh/glove_states`
- Left glove:
  - Device/glove ID: `67`
  - ROS topic when used alone: `/r1/glove67/lh/glove_states`

### Shadow side

- Host laptop OS: Ubuntu 20.04.4 LTS
- ROS: ROS 1 Noetic inside Docker
- Docker container: `dexterous_hand_real_hw`
- Docker image: `public.ecr.aws/shadowrobot/dexterous-hand:noetic-release`
- Target command topic discovered for the finger trajectory controller:
  - `/rh_trajectory_controller/command`

### Discovered Shadow Hand Lite joint set

The discovered right-hand reduced/Lite configuration has 12 active joints:

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

Grouped by finger:

```text
rh_FFJ* → Shadow first finger
rh_RFJ* → Shadow ring finger
rh_THJ* → Shadow thumb
```

---

## What Works Today

The R1-side dry-run pipeline works through explicit internal stages:

```text
R1 glove topic
        ↓
RawHandState from normalized_finger_positions
        ↓
CalibratedHandState with flexion plus display-only abduction diagnostics
        ↓
MappedShadowTargetState, calibrated flexion only
        ↓
FilteredShadowTargetState, pass-through for now
        ↓
OutgoingCommandPreview with JointTrajectory and dry-run packet
        ↓
latest_command_packet.json
```

Validated items:

- The R1 simulator works.
- The right R1 glove works alone.
- The left R1 glove works alone.
- The right R1 glove publishes live messages on `/r1/glove69/rh/glove_states`.
- The useful R1 field is `normalized_finger_positions`.
- The first five values are flexion values in this order:
  1. thumb
  2. index
  3. middle
  4. ring
  5. pinky
- The values are in the range `0..10000`, so the first parser scales them to `0.0..1.0`.
- Abduction is reported for diagnostics only and is not used for Shadow mapping yet.
- A pose calibration CSV was collected for the right glove.
- A calibrated dry-run mapping is implemented.
- A Shadow `JointTrajectory` preview is generated.
- A dry-run JSON command packet is generated.
- A print-only Shadow receiver/sender script can read and validate the packet.
- The current sender refuses to publish because the packet is marked dry-run only.

---

## What Does Not Work Yet

The following are **not implemented** or **not validated** yet:

- No live LAN transport yet.
- No UDP/TCP network bridge yet.
- No ROS 1 publishing to the Shadow Hand yet.
- No physical Shadow Hand motion from the SenseGlove yet.
- No deadman switch yet.
- No stale-packet timeout yet.
- No final joint-limit enforcement from Shadow URDF/controller limits yet.
- No force feedback.
- No tested bidirectional communication.
- No full ROS 1 ↔ ROS 2 bridge.

Two-glove R1 mode is also unresolved. Linux sees both gloves and each glove works alone, but `SG_main.init(2, REAL_GLOVE_USB)` blocks while waiting for the second glove. This appears to be below the ROS layer in the SenseGlove SDK/API initialization path.

---

## Hardware and Software Setup

### R1 workspace activation

Use this on the R1 Ubuntu machine:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
```

Expected output includes:

```text
R1 environment active
ROS_DISTRO=jazzy
VIRTUAL_ENV=/home/gerard/r1_ws/.venv
```

### R1 launch

Right glove only:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 launch r1_bringup r1.launch.py
```

The SenseGlove GUI should open and show the right hand moving.

### R1 topic

Current right glove topic:

```text
/r1/glove69/rh/glove_states
```

---

## Current Finger Mapping

The Shadow Hand Lite has fewer fingers than the R1 glove. For the current prototype we map only the R1 fingers that correspond cleanly to the discovered Shadow groups:

| R1 glove input | Shadow group | Shadow joints | Status |
|---|---|---|---|
| Thumb | Thumb | `rh_THJ1`, `rh_THJ2`, `rh_THJ4`, `rh_THJ5` | Used |
| Index | First finger | `rh_FFJ1`, `rh_FFJ2`, `rh_FFJ3`, `rh_FFJ4` | Used |
| Ring | Ring finger | `rh_RFJ1`, `rh_RFJ2`, `rh_RFJ3`, `rh_RFJ4` | Used |
| Middle | — | — | Ignored for now |
| Pinky | — | — | Ignored for now |

Possible future experiments:

- Map R1 middle + ring average to Shadow ring.
- Map R1 ring + pinky average to Shadow ring.
- Add per-finger response curves.
- Add thumb-specific tuning for natural open posture.

---

## Current Data Pipeline

### R1 message field

`r1_msgs/msg/R1GloveState` includes:

```text
normalized_finger_positions
```

The relevant order is:

```text
[
  flexion_thumb,
  flexion_index,
  flexion_middle,
  flexion_ring,
  flexion_pinky,
  abduction_thumb,
  abduction_index,
  abduction_middle,
  abduction_ring,
  abduction_pinky
]
```

The documented range is:

```text
0..10000
```

The current code scales raw values by dividing by `10000.0`, then applies calibration:

```text
calibrated = (raw_scaled - open_baseline) / (closed_baseline - open_baseline)
```

The result is clamped to:

```text
0.0..1.0
```

### Shadow command shape

The generated Shadow command preview uses ordered joint names and one trajectory point:

```text
JointTrajectory
  joint_names: [12 Shadow joint names]
  points[0].positions: [12 joint values in same order]
  points[0].time_from_start: 2.0 sec
```

The current preview is built but **not published**.

---

## Repository Layout

Current important paths:

```text
r1_shadow_teleop/
├── README.md
├── package.xml
├── setup.py
├── runtime_data/
│   ├── senseglove_r1/
│   │   └── calibrations/    # generated CSV/JSON/registry files, gitignored
│   └── shadow_hand/         # generated dry-run command packet, gitignored
├── r1_shadow_teleop/
│   ├── senseglove_r1/       # R1 frame parsing and raw calibration printer
│   ├── calibration/         # capture, poses, registry, resolver, diagnostics
│   ├── dashboard/           # listener/display node
│   └── shadow_hand/         # dry-run Shadow Hand preview packet helpers
├── tools/
└── docs/
```

This documentation set should be placed in:

```text
~/r1_ws/src/r1_shadow_teleop/
```

with `README.md` at the repository root and the other Markdown files under `docs/`.

---

## Important Code Modules

### `senseglove_r1/`

SenseGlove R1-specific code. `frame.py` parses the ROS 2 glove message into a hand frame, and `calibration_printer.py` prints raw normalized glove values for inspection.

### `calibration/`

Calibration lifecycle code: data models, default paths, pose definitions, terminal UI helpers, capture/range computation, JSON sidecar and registry storage, active resolver selection, and abduction diagnostics.

### `dashboard/listener_node.py`

Main R1-side dry-run listener. It subscribes to `/r1/glove69/rh/glove_states`, applies active calibration, shows calibration-source and abduction diagnostics, builds a dry-run Shadow Hand preview, and saves `runtime_data/shadow_hand/latest_command_packet.json`.

### `shadow_hand/`

Dry-run Shadow Hand preview helpers. These modules map calibrated R1 flexion to preview targets, build a `JointTrajectory` message shape, and serialize the current preview packet. They do not publish to the robot.

### `tools/`

Print-only and safety-gated Shadow-side helper scripts for moving preview packets between machines. Live publishing remains out of scope.

---

## Quick Start: R1 Machine

### Terminal 1: start the R1 glove

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 launch r1_bringup r1.launch.py
```

Expected:

- GUI opens.
- Right glove hand model moves.
- `/r1/glove69/rh/glove_states` publishes.

### Terminal 2: run calibrated dry-run listener

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop senseglove_r1_listener
```

Expected output includes:

```text
R1 → Shadow calibrated dry-run mapping
Human-readable Shadow preview:
  Shadow first finger from R1 index: ...
  Shadow ring finger  from R1 ring:  ...
  Shadow thumb        from R1 thumb: ...
Shadow JointTrajectory preview, NOT publishing:
```

It should also write:

```text
~/r1_ws/src/r1_shadow_teleop/runtime_data/shadow_hand/latest_command_packet.json
```

### Run calibration printer

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop senseglove_r1_calibration_printer
```

### Run calibration utility

Interactive guided calibration:

```bash
cd ~/r1_ws
source ~/r1_ws/activate_r1.sh
ros2 run r1_shadow_teleop senseglove_r1_calibration
```

The utility prompts for hand, mode, selected fingers, and output location. For each pose it shows a separated step panel with explicit, comfort-focused instructions, waits for Enter, shows settle/sample progress based on `settle_seconds` and `sample_seconds`, shows a compact summary, then asks:

```text
Enter/a = accept and continue
r       = repeat this pose
s       = skip optional pose
q       = abort safely
```

Each complete run writes timestamped CSV/JSON files under the package-local calibration directory and updates stable latest files there:

```text
runtime_data/senseglove_r1/calibrations/r1_right_glove_calibration_2026-05-26_143012.csv
runtime_data/senseglove_r1/calibrations/r1_right_glove_calibration_latest.csv
```

New calibration runs write to `runtime_data/senseglove_r1/calibrations/` by default. Generated CSV/JSON/registry files are ignored by Git, and each saved run updates the package-local registry:

```text
runtime_data/senseglove_r1/calibrations/calibration_registry.json
```

Longer timing example:

```bash
ros2 run r1_shadow_teleop senseglove_r1_calibration --ros-args -p settle_seconds:=1.5 -p sample_seconds:=4.0
```

Useful non-interactive setup examples:

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

The listener also reports the active dry-run teleop config. Phase 6 supports SenseGlove R1 input only, with these defaults:

```text
input_source=senseglove_r1
input_hand=right
target_hand=right
shadow_hand_model=hand_lite_3finger
mirror_mode=none
```

`shadow_hand_model:=hand_full_5finger` is accepted as known future metadata, but the current preview mapping is still the existing Hand Lite-style thumb/first/ring dry-run mapping. Unsupported input sources or mirror modes fail clearly instead of silently changing behavior.

Phase 7 makes the dry-run pipeline explicit in the listener: raw hand state, calibrated hand state, mapped Shadow target state, pass-through filtered state, and outgoing command preview. The listener reports `mapping_profile: hand_lite_3finger_placeholder`, `mapped_from: calibrated_flexion`, `abduction_used_for_shadow_mapping: false`, and `filter_profile: pass_through`.

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

Run the listener with an explicit calibration file. Explicit paths still override the registry resolver and use only that CSV plus its sidecar:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener --ros-args -p calibration_csv_path:=runtime_data/senseglove_r1/calibrations/r1_right_glove_calibration_YYYY-MM-DD_HHMMSS.csv
```

Run the listener in plain/no-color mode:

```bash
ros2 run r1_shadow_teleop senseglove_r1_listener --ros-args -p use_rich:=false -p color_output:=false
```

Abduction note: raw/sdk abduction is directional SDK data. The listener also shows the calibration neutral baseline, signed offset from neutral, spread, and an abduction status. Spread is shown only when schema v2 calibration metadata is reliable; missing quality metadata or warnings mean recalibration is recommended.

### Create Shadow print-only transfer bundle

Make sure `senseglove_r1_listener` has generated a current packet first.

```bash
cd ~/r1_ws/src/r1_shadow_teleop
tools/make_shadow_print_bundle.sh
```

Expected output:

```text
/home/gerard/shadow_print_only_bundle_<timestamp>.tar.gz
```

Transfer that `.tar.gz` to the Shadow laptop by USB or network.

---

## Quick Start: Shadow Print-Only Bundle

After transferring the bundle to the Shadow laptop:

```bash
mkdir -p ~/shadow_print_only_test
tar -xzf ~/shadow_print_only_bundle_*.tar.gz -C ~/shadow_print_only_test

cd ~/shadow_print_only_test/r1_shadow_teleop

python3 tools/shadow_ros1_sender.py   --packet runtime_data/shadow_hand/latest_command_packet.json
```

Expected ending:

```text
Not publishing because --publish was not provided.
```

Safety refusal test:

```bash
python3 tools/shadow_ros1_sender.py   --packet runtime_data/shadow_hand/latest_command_packet.json   --publish   --i-understand-this-can-move-the-robot
```

Expected ending:

```text
Refusing to publish: packet safety flags do not allow robot motion.
Required: safety.publish_to_robot=true and safety.dry_run_only=false
```

Inside Docker:

```bash
docker ps --format 'table {{.Names}}	{{.Image}}	{{.Status}}'

docker cp ~/shadow_print_only_test/r1_shadow_teleop   dexterous_hand_real_hw:/tmp/r1_shadow_teleop_print_test

docker exec -it dexterous_hand_real_hw bash
```

Inside the container:

```bash
cd /tmp/r1_shadow_teleop_print_test

python3 tools/shadow_ros1_sender.py   --packet runtime_data/shadow_hand/latest_command_packet.json
```

Expected ending:

```text
Not publishing because --publish was not provided.
```

---

## Calibration Summary

Current right-glove calibration was collected from pose averages.

| Pose | Thumb | Index | Middle | Ring | Pinky |
|---|---:|---:|---:|---:|---:|
| Open relaxed | 0.376 | 0.185 | 0.168 | 0.196 | 0.187 |
| Full fist | 0.818 | 0.814 | 1.000 | 1.000 | 1.000 |
| Thumb only | 1.000 | 0.163 | 0.071 | 0.142 | 0.140 |
| Index only | 0.514 | 0.934 | 0.291 | 0.171 | 0.145 |
| Middle only | 0.533 | 0.156 | 0.918 | 0.326 | 0.166 |
| Ring only | 0.531 | 0.118 | 0.272 | 0.894 | 0.133 |
| Pinky only | 0.545 | 0.175 | 0.078 | 0.602 | 0.778 |

Current closed baselines use isolated-finger poses where available:

```text
thumb  → thumb_only
index  → index_only
middle → middle_only
ring   → ring_only
pinky  → pinky_only
```

Notes:

- Thumb natural-open behavior may need tuning.
- Pinky and ring are mechanically/biologically coupled during some motions.
- Middle and pinky are not used in the current Shadow mapping.

---

## Generated Files

These are generated runtime artifacts and generally should not be committed:

```text
runtime_data/shadow_hand/latest_command_packet.json
```

Runtime calibration CSV/JSON/registry files live under `runtime_data/senseglove_r1/calibrations/`. The generated files are ignored by Git; only the directory placeholder is kept in the repository.

The Shadow print-only bundle should not be committed:

```text
~/shadow_print_only_bundle_<timestamp>.tar.gz
```

---

## Known Issues and Open Questions

### Two-glove R1 initialization

Symptoms:

- Linux sees both gloves.
- Each glove works alone.
- `ros2 launch r1_bringup r1.launch.py num_gloves:=2` starts but creates no glove topics.
- Direct API test `SG_main.init(2, REAL_GLOVE_USB)` detects one glove and blocks waiting for the second.

Current interpretation:

- The issue appears below the ROS wrapper, likely in SDK/API multi-device initialization.

Status:

- Support packet prepared.
- Email to SenseGlove Support drafted separately.

### Thumb calibration

Natural thumb-open posture may produce a nonzero calibrated value. This is expected and can be tuned later with:

- open baseline adjustment
- dead zone
- response curve
- separate thumb mapping

### Shadow command safety

The current code does not know final verified joint limits from the Shadow URDF/controller configuration. Before physical publishing, add:

- joint clamps from verified limits
- rate limiting
- smoothing
- deadman switch
- stale-packet timeout
- known safe open-hand command

---

## Next Steps

The current application remains **dry-run only**. Do not treat UDP/TCP transport,
ROS bridge work, or live Shadow publishing as the immediate next task.

Recommended order:

1. Expand the Shadow Hand model/config layer using real Shadow-side evidence for the current `hand_lite_3finger` setup.
2. Collect and document controller topics, active joints, joint order, joint limits, `/joint_states`, and safe neutral/open postures from the Shadow ROS 1/Docker environment.
3. Replace placeholder mapping with model-driven dry-run mapping and validation.
4. Add dry-run safety checks for stale packets, wrong joint order, out-of-range values, sudden jumps, and unsafe defaults.
5. Only after dry-run validation and safety design should transport/bridge work or guarded live publishing to `/rh_trajectory_controller/command` be considered.

The canonical active roadmap is `docs/current_roadmap.md`. The completed Phase 1-7 refactor plan is archived at `docs/archive/refactor_plan_phases_1_7.md`.

---

## References

- ROS 2 `trajectory_msgs/msg/JointTrajectory`: https://docs.ros2.org/foxy/api/trajectory_msgs/msg/JointTrajectory.html
- ROS 1 Noetic `trajectory_msgs/JointTrajectory`: https://docs.ros.org/en/noetic/api/trajectory_msgs/html/msg/JointTrajectory.html
- Shadow Dexterous Hand command-line docs, finger trajectory controller: https://shadow-robot-company-dexterous-hand.readthedocs-hosted.com/en/2.2.4/user_guide/sd_command_line.html
- ROS 2 joint trajectory controller overview: https://control.ros.org/master/doc/ros2_controllers/joint_trajectory_controller/doc/userdoc.html
