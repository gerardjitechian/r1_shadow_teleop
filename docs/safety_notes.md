# Safety Notes

## Table of Contents

- [Current Safety Position](#current-safety-position)
- [Current Software Gates](#current-software-gates)
- [Do Not Do Yet](#do-not-do-yet)
- [Before Any Physical Shadow Motion](#before-any-physical-shadow-motion)
- [Required Runtime Safety Features](#required-runtime-safety-features)
- [First Motion Test Plan](#first-motion-test-plan)
- [Emergency Stop Expectations](#emergency-stop-expectations)
- [Force Feedback Safety](#force-feedback-safety)
- [Shutdown Safety](#shutdown-safety)

---

## Current Safety Position

The project is currently in **dry-run mode**.

Current code can:

- read R1 glove state
- map glove motion to Shadow target values
- build a `JointTrajectory` preview
- write a JSON packet
- print a Shadow-side command preview

Current code should not move the physical Shadow Hand.


Roadmap reference: `docs/current_roadmap.md` is the canonical active plan for
when transport, filtering, guarded publishing, and closed-loop safety work should
be introduced. Those items are future work, not current live behavior.

---

## Current Software Gates

Current R1-generated packets contain:

```json
{
  "safety": {
    "dry_run_only": true,
    "publish_to_robot": false
  }
}
```

The guarded ROS 1 sender requires:

```text
--publish
--i-understand-this-can-move-the-robot
safety.publish_to_robot == true
safety.dry_run_only == false
```

Current packets intentionally fail those gates.

This is correct.

---

## Do Not Do Yet

Do not manually edit packets to enable publishing.

Do not publish live glove commands to the Shadow Hand.

Do not test force feedback.

Do not bypass the sender safety checks.

Do not run physical motion without confirming emergency stop procedure.

Do not use large joint values for first motion.

Do not use fast trajectory durations for first motion.

---

## Before Any Physical Shadow Motion

Complete this checklist first:

```text
[ ] Confirm emergency stop procedure.
[ ] Confirm hand power control procedure.
[ ] Confirm how to stop ROS/Shadow controller safely.
[ ] Confirm current Shadow container is correct.
[ ] Confirm target topic is /rh_trajectory_controller/command.
[ ] Confirm active joint list.
[ ] Confirm joint limits from Shadow configuration.
[ ] Confirm controller state topic is available.
[ ] Confirm no demos are running.
[ ] Confirm hand starts in a safe posture.
[ ] Confirm all commands are clamped.
[ ] Confirm command rate limit is active.
[ ] Confirm stale-packet timeout is active.
[ ] Confirm deadman switch exists and defaults to inactive.
[ ] Confirm first command is known-safe open posture.
```

---

## Required Runtime Safety Features

Before live teleoperation:

### Deadman switch

Robot motion should require an explicit active signal.

Default:

```text
deadman inactive → no publishing
```

### Stale-packet timeout

If no fresh command arrives, stop publishing or send safe hold/open behavior.

Suggested first timeout:

```text
0.5 sec
```

### Joint clamps

Every joint value should be clamped to verified safe limits.

Do not rely on R1 values alone.

### Rate limiting

Limit how quickly commanded joint values can change.

### Smoothing

Avoid abrupt jumps from calibration noise or dropped packets.

### Sequence numbers

Packets should include a sequence number so the receiver can detect stale/out-of-order data.

### Timestamp

Packets should include creation time so receiver can reject old commands.

### Logging

Log:

- packet receive rate
- publish rate
- stale packet events
- clamp events
- deadman status
- command topic
- active joint names

---

## First Motion Test Plan

The first physical motion test should not use live glove input.

### Test 1: known safe open command

Command an open or neutral hand posture slowly.

Expected:

```text
No sudden motion.
No unexpected finger group moves.
Controller accepts command.
```

### Test 2: tiny first-finger motion

Move only the Shadow first finger slightly.

Suggested first target:

```text
rh_FFJ1: 0.1
rh_FFJ2: 0.1
rh_FFJ3: 0.1
rh_FFJ4: 0.0
```

Suggested duration:

```text
2–3 sec
```

### Test 3: return to open

Return to safe open posture.

### Test 4: tiny ring finger motion

Only after first-finger motion is safe.

### Test 5: tiny thumb motion

Only after first/ring tests are safe.

### Test 6: live teleop

Only after known static commands are safe.

---

## Emergency Stop Expectations

Before enabling physical publishing, the operator should know:

- how to stop the sender process
- how to stop the Shadow Docker process if needed
- how to disable hand power
- how to use any physical emergency stop
- who is responsible for watching the hand
- what to do if the hand moves unexpectedly

Minimum emergency stop action during development:

```text
Ctrl+C sender process
```

But this is not enough by itself for full safety. Hardware/power stop procedure must be known.

---

## Force Feedback Safety

Force feedback is not implemented yet.

Do not send R1 force commands until:

- one-way motion teleoperation is stable
- Shadow tactile signals are understood
- force limits are defined
- force command topic behavior is verified
- force feedback can be disabled instantly
- emergency stop procedure is confirmed

Possible future R1 force command topic:

```text
/r1/glove69/rh/force_commands
```

Possible future Shadow feedback topics:

```text
/rh/tactile
/rh/palm_extras
/rh_trajectory_controller/state
/joint_states
```

---

## Shutdown Safety

Before shutting down:

1. Stop live scripts with `Ctrl+C`.
2. Stop ROS launch files.
3. Confirm no command publisher is running.
4. Close Shadow apps.
5. Shut down laptop/NUC normally.
6. Disconnect hand power only after software shutdown.
