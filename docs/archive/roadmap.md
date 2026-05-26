# Project Roadmap

> Historical note: this archived roadmap may use old phase numbering and older bridge timing. The current active roadmap is `../refactor_plan.md`.

## Table of Contents

- [North Star Goal](#north-star-goal)
- [Scope: Current Phase](#scope-current-phase)
- [Architecture Direction](#architecture-direction)
- [Completed Phases](#completed-phases)
- [Immediate Next Phase](#immediate-next-phase)
- [Live Network Bridge Plan](#live-network-bridge-plan)
- [Publishing Plan](#publishing-plan)
- [Real Hardware Motion Plan](#real-hardware-motion-plan)
- [Tuning Plan](#tuning-plan)
- [Force Feedback: Later Phase](#force-feedback-later-phase)
- [Open Design Decisions](#open-design-decisions)
- [Definition of Done Milestones](#definition-of-done-milestones)

---

## North Star Goal

The long-term goal is intuitive teleoperation of the Shadow Hand using the SenseGlove R1.

Initial one-way motion goal:

```text
User moves right SenseGlove R1
        ↓
R1 machine receives glove state in ROS 2
        ↓
software extracts calibrated thumb/index/ring motion
        ↓
commands are sent over the lab network
        ↓
Shadow ROS 1 container receives commands
        ↓
Shadow Hand Lite moves thumb/first/ring fingers
```

This phase does not include force feedback.

---

## Scope: Current Phase

Current scope:

```text
Motion teleoperation only
Right glove only
Right Shadow Hand Lite only
Thumb/index/ring mapping only
Dry-run and safety-gated development
```

Out of scope for now:

```text
Force feedback
Two-glove control
Full five-finger Shadow Hand mapping
High-speed hard real-time control
Autonomous grasping
Learning-based control
```

---

## Architecture Direction

Preferred first real bridge:

```text
UDP JSON transport
```

Reason:

- The R1 side is ROS 2 Jazzy on Ubuntu 24.04.
- The Shadow side is ROS 1 Noetic inside Docker on Ubuntu 20.04.
- A full ROS 1 ↔ ROS 2 bridge across these environments may be more fragile than needed for the first prototype.
- Teleoperation is a latest-state problem: stale packets should be dropped, not queued.

Expected live architecture:

```text
R1 ROS 2 node
  subscribes to /r1/glove69/rh/glove_states
  calibrates values
  maps to Shadow target
  sends latest command packet over UDP

Shadow receiver
  listens on UDP port
  validates packet
  checks safety conditions
  converts packet to JointTrajectory
  publishes only if enabled and safe
```

---

## Completed Phases

### Phase 0: Environment setup

Completed:

- ROS 2 Jazzy R1 workspace built.
- SenseGlove R1 ROS wrapper built.
- R1 simulator verified.
- Right R1 glove verified.
- Left R1 glove verified individually.
- GitHub repository created and pushed.

### Phase 1: R1 message parsing

Completed:

- Right glove topic identified:
  - `/r1/glove69/rh/glove_states`
- Useful field identified:
  - `normalized_finger_positions`
- Field order confirmed:
  - thumb, index, middle, ring, pinky flexion first
- Scaling identified:
  - `0..10000` → `0.0..1.0`

### Phase 2: Calibration

Completed:

- Pose recorder implemented.
- Right-glove calibration CSV collected.
- Open/closed baselines implemented.
- Calibrated flexion values generated.

### Phase 3: Shadow mapping

Completed:

- R1 thumb → Shadow thumb
- R1 index → Shadow first finger
- R1 ring → Shadow ring finger
- 12-joint Shadow target vector generated.

### Phase 4: Shadow command preview

Completed:

- `JointTrajectory` preview generated.
- Dry-run command packet generated.
- Print-only Shadow receiver/sender skeleton implemented.
- Publishing safety gates implemented.

---

## Immediate Next Phase

### Phase 5: Shadow-side print-only validation

Goal:

```text
Move bundle from R1 machine to Shadow laptop
Run print-only sender outside Docker
Run print-only sender inside Docker
Confirm refusal to publish
```

Success criteria:

- Packet is readable on Shadow laptop.
- Packet is readable inside Docker container.
- Joint names validate.
- Print-only output shows the correct command topic.
- Safety refusal works.

No robot movement.

---

## Live Network Bridge Plan

### Phase 6: UDP print-only bridge

Goal:

```text
R1 machine sends live UDP packets
Shadow laptop/container receives live UDP packets
Shadow side prints command previews only
```

Suggested starting rate:

```text
10 Hz
```

Then test:

```text
20 Hz
```

Possible later rate:

```text
30–50 Hz
```

Design rules:

- Use latest packet only.
- Drop stale packets.
- Include sequence number.
- Include timestamp.
- Include safety mode.
- Include command duration.
- Validate joint names every time or at connection start.
- Do not publish yet.

Packet fields to include:

```json
{
  "type": "shadow_joint_trajectory_command",
  "schema_version": 1,
  "sequence": 123,
  "created_utc": "...",
  "source": "r1_glove69_rh",
  "safety": {
    "dry_run_only": true,
    "publish_to_robot": false,
    "deadman_active": false
  },
  "trajectory": {
    "joint_names": ["..."],
    "positions": [0.0],
    "duration_sec": 0.2
  }
}
```

---

## Publishing Plan

### Phase 7: ROS 1 publisher, safety-gated

Goal:

```text
Shadow receiver can publish, but only under strict gates.
```

Required safety conditions before publishing:

- Explicit publish flag.
- Packet publish flag.
- Packet not dry-run.
- Deadman active.
- Packet timestamp fresh.
- Joint names exactly match expected list.
- Position count exactly matches joint count.
- All positions within verified safe clamps.
- Rate limit active.
- Known emergency stop procedure confirmed.

Initial publishing target:

```text
/rh_trajectory_controller/command
```

Initial command should be:

```text
known safe open-hand command
```

not live glove motion.

---

## Real Hardware Motion Plan

### Phase 8: Known safe open command

Send only an open/neutral command.

Goal:

```text
Confirm the Shadow Hand accepts a trajectory command safely.
```

### Phase 9: Tiny single-finger motion

Move one finger group slightly and slowly.

Recommended first test:

```text
rh_FFJ1
rh_FFJ2
rh_FFJ3
```

Small target:

```text
0.1–0.2 rad
```

Slow duration:

```text
2–3 seconds
```

Do not start with thumb or multi-finger motion.

### Phase 10: Live glove teleoperation

Only after prior phases pass:

```text
R1 calibrated values
        ↓
UDP packets at 10–20 Hz
        ↓
Shadow receiver safety gates
        ↓
ROS1 JointTrajectory publish
```

Safety features required:

- deadman
- stale timeout
- command clamps
- rate limiting
- smoothing
- logging
- emergency stop procedure

---

## Tuning Plan

Tuning items:

### Calibration

- open baseline
- closed baseline
- per-finger dead zone
- per-finger response curve
- thumb-specific open posture
- ring/pinky coupling handling

### Mapping

Current:

```text
thumb → thumb
index → first finger
ring  → ring finger
```

Future experiments:

```text
ring = R1 ring
ring = average(R1 ring, R1 pinky)
ring = average(R1 middle, R1 ring)
```

### Trajectory duration

Current preview:

```text
2.0 sec
```

Potential live values:

```text
10 Hz command rate → 0.2 sec trajectory duration
20 Hz command rate → 0.1 sec trajectory duration
```

Tune slowly and safely.

---

## Force Feedback: Later Phase

Force feedback should be treated as a separate project phase.

Prerequisites:

- stable one-way teleoperation
- understood Shadow tactile topics
- stable command rate
- safety clamps for feedback forces
- verified R1 force command behavior
- emergency stop procedure

Possible future feedback sources:

```text
/rh/tactile
/rh/palm_extras
/rh_trajectory_controller/state
/joint_states
```

Possible R1 output topic:

```text
/r1/glove69/rh/force_commands
```

Do not start force feedback until motion-only teleoperation is stable.

---

## Open Design Decisions

- UDP vs TCP vs WebSocket for live bridge.
- Whether Shadow receiver runs on host laptop or inside Docker.
- How to implement deadman input.
- Exact Shadow joint limits.
- Whether to use trajectory commands or individual position controller topics.
- How much smoothing to apply.
- Best mapping for the Shadow ring finger.
- Whether to create a ROS package on the Shadow side or keep a standalone script.

---

## Definition of Done Milestones

### Print-only handoff done

- Bundle tested outside Docker.
- Bundle tested inside Docker.
- Safety refusal confirmed.

### UDP bridge print-only done

- R1 sends live packets.
- Shadow receives live packets.
- Values update with glove movement.
- No publishing.

### Safe publisher skeleton done

- Can publish only known safe open command.
- Deadman exists.
- Stale timeout exists.
- Clamps exist.
- Logging exists.

### First physical motion done

- Known safe open command works.
- Tiny first-finger motion works.
- No unexpected motion.

### Live teleop prototype done

- Thumb/index/ring live movement works.
- Motion is slow, clamped, and smooth.
- Deadman stops motion.
- Stale packets stop motion.
- No force feedback yet.
