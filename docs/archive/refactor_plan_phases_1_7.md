# Archived Refactor Plan, Phases 1-7

> Historical note: this plan tracked the staged refactor through Phase 7. Phases 1-7 are complete. The current active roadmap is [docs/current_roadmap.md](../current_roadmap.md).

# Staged Refactor Plan

## Summary

Stage this as an architecture and calibration reliability refactor before any new
Shadow control work. The first priorities should be preserving behavior, moving
runtime data out of `docs/`, and making active calibration resolution explicit.
Only after that should the listener UX, abduction diagnostics, and package
structure expand toward future Shadow mapping/filtering/transport boundaries.

Recommended order:

1. Runtime paths and calibration storage foundation
2. Calibration registry and active calibration resolver
3. Listener diagnostics and calibration-source reporting
4. Calibration terminal UX and pose prompt rewrite
5. Package/module reorganization with new command names
6. Shadow model/config scaffolding only
7. Future pipeline boundaries for filtering/transport, still dry-run only

## Phase 1: Runtime Paths And Backward Compatibility

**Goal:** Move generated calibration data out of `docs/` without breaking
existing files.

**Why first:** Storage location affects calibration capture, listener defaults,
docs, and tests. It should be stabilized before changing registry semantics.

**Plan:**

- Add a runtime path helper with default calibration dir:
  `runtime_data/senseglove_r1/calibrations/`
- New writes go to `runtime_data/senseglove_r1/calibrations/`.
- Keep explicit path loading available for one-off files.
- Old-location compatibility is not a priority after Phase 5; run a fresh calibration.

**Likely changes:**

- `r1_shadow_teleop/calibration/`
- `r1_shadow_teleop/calibration/tool_node.py`
- `r1_shadow_teleop/dashboard/listener_node.py`
- README/runbook references

**Must not change in this phase:**

- Calibration math
- Pose sequence
- Shadow preview mapping
- ROS entry points

**Checks:**

- `python3 -m py_compile r1_shadow_teleop/*.py`
- `colcon build --symlink-install --packages-select r1_shadow_teleop`
- Listener can load an explicit CSV path when supplied.
- Calibration tool writes a new file to
  `runtime_data/senseglove_r1/calibrations/`.

## Phase 2: Calibration Records, Registry, And Active Resolver

**Goal:** Replace “load one latest file” behavior with explicit active
calibration resolution.

**Implementation status:** Phase 2 adds schema v2 sidecars,
`calibration_registry.json`, and listener resolver modes `explicit_file`,
`latest_complete`, and `composed_latest`. The default listener resolver is
`composed_latest`.

**Recommended storage:** JSON sidecars plus a JSON registry/manifest.

Use:

- Per-run CSV: raw sampled rows, same basic role as today.
- Per-run JSON sidecar: canonical calibration record metadata and computed
  ranges.
- Registry file:
  `runtime_data/senseglove_r1/calibrations/calibration_registry.json`.

Resolver modes:

- `explicit_file`: use only `calibration_csv_path`/sidecar
- `latest_complete`: newest non-aborted run containing complete flexion and
  abduction for all selected fingers
- `composed_latest`: newest valid record per input hand + dimension + finger

Aborted records may be written for audit, but never selected as active. Partial
accepted records may contribute only the dimensions/fingers they validly
captured.

## Phase 3: Listener Calibration Reporting And Abduction Diagnostics

**Goal:** Make listener output truthful about what values mean.

Implemented focus: show raw/sdk abduction separately from calibration-relative diagnostics:

- raw/sdk abduction
- neutral baseline
- signed offset from neutral
- calibrated spread magnitude only when reliable
- abduction reliability/status

The listener now reports resolver mode, source type, contributing files, registry path, and complete/partial/degraded status. New schema v2 sidecars include optional structured abduction quality metadata. Missing quality metadata produces limited/degraded diagnostics and recommends recalibration.

## Phase 4: Calibration Terminal UX And Anatomy-Grounded Prompts

**Goal:** Improve calibration capture clarity and safety.

Implemented focus: use optional Rich terminal helpers with plain text fallback.
The calibration tool now shows separated run/pose panels, timed settle/sample
progress based on `settle_seconds` and `sample_seconds`, clearer invalid input
messages, clean abort messaging, and safer prompts that specify target scope,
thumb/non-target finger posture, relaxed/open/curled state, natural coupling,
and avoidance of forced hyperextension or strain.

## Phase 5: Package/Module Reorganization

**Goal:** Reduce the flat proof-of-concept structure and adopt explicit SenseGlove R1 command names.

Approved Phase 5 structure:

```text
r1_shadow_teleop/
  senseglove_r1/
    frame.py
    calibration_printer.py

  calibration/
    models.py
    defaults.py
    poses.py
    terminal_ui.py
    capture.py
    storage.py
    resolver.py
    diagnostics.py
    tool_node.py

  dashboard/
    listener_node.py

  shadow_hand/
    mapping_preview.py
    trajectory.py
    command_packet.py
```

Approved command names:

- `ros2 run r1_shadow_teleop senseglove_r1_calibration`
- `ros2 run r1_shadow_teleop senseglove_r1_listener`
- `ros2 run r1_shadow_teleop senseglove_r1_calibration_printer`

Use `senseglove_r1/` for SenseGlove R1 code and `shadow_hand/` for Shadow
Dexterous Hand / Shadow Hand code. Phase 5 may split calibration modules
thoughtfully, but should avoid tiny awkward modules and circular imports. Old
internal compatibility is not the priority; clear new usage is. Future
bridge/transport/filtering work remains deferred and should not create empty
placeholder packages in this phase.

## Phase 6: Input-Aware Shadow Hand Model/Configuration Scaffolding

**Goal:** Represent input source and target hand configuration without implementing control.

Phase 6 adds typed dry-run config concepts for:

- `input_source`, currently only `senseglove_r1`
- `input_hand`, `right` or `left`
- `target_hand`, `right` or `left`
- `shadow_hand_model`, `hand_lite_3finger` or `hand_full_5finger`
- `mirror_mode`, currently only `none`

The default remains `senseglove_r1/right -> right hand_lite_3finger`.
`hand_full_5finger` is recognized as future model metadata only; the current
preview mapping remains the existing dry-run Hand Lite-style thumb/first/ring
mapping. Unsupported input sources and mirror modes should fail clearly. No Meta
Quest, vision-tracking, bridge, transport, filtering, PID, or live publishing
code belongs in this phase.

## Phase 7: Future Pipeline Boundaries Only

**Goal:** Prepare clean internal state boundaries for later filtering, mapping,
and transport.

Define lightweight interfaces for:

- raw glove state
- calibrated glove state
- mapped Shadow target state
- filtered target state
- outgoing command packet/trajectory

Do not implement filtering, PID, networking, bridges, abduction-to-Shadow
mapping, or live publishing in this phase. Filtering is represented as an
explicit `pass_through` stage only, and the listener should report that current
Shadow preview mapping uses calibrated flexion only.

## Post-Phase-7 Roadmap

Phase 6 remains limited to Shadow Hand model/config scaffolding. Phase 7 remains
limited to internal pipeline boundaries. The work below belongs to later phases;
it should not be folded into Phase 6 or Phase 7.

### Shadow Hand Model/Config Expansion

Expand the Phase 6 scaffolding into real model-specific configuration for the
current right `hand_lite_3finger`-style Shadow Hand and future
`hand_full_5finger` setups. Keep `input_source`, `input_hand`, `target_hand`,
`shadow_hand_model`, and `mirror_mode` explicit so input adapter choice,
left/right target choice, and mirror-control choices do not leak into hardcoded
mapping logic.

### Mapping Profiles And Joint Validation

Move from the current dry-run placeholder mapping toward model-specific mapping
profiles. Validate joint order, active joints, expected controller names, and
joint limits against the discovered Shadow configuration before any physical
motion. Include safe default/open positions as named data, not ad hoc constants.

### Dry-Run Safety Validation

Keep validating packets and trajectory shapes without publishing. Add checks for
safe default positions, joint order, joint-limit clamps, stale data, and sudden
jumps before enabling any command path that can move hardware.

### Transport/Bridge Layer

Design the ROS 2 SenseGlove R1 to ROS 1 Shadow Hand boundary after the internal
state pipeline is clear. Candidate approaches include UDP, TCP, a custom packet
bridge, or a ROS 1/ROS 2 bridge. This transport/bridge work is post-Phase-7, not
part of Phase 6 or Phase 7.

### Shadow-Side Dry-Run Receiver

Evolve the current print-only Shadow-side tools into a receiver that can accept
live packets and continue to print/validate them without publishing. This should
exercise timing, stale-packet handling, packet versioning, and safety refusal
behavior before any live publishing is added.

### Guarded Live Publishing

Only after dry-run safety validation should a Shadow-side process publish to
`/rh_trajectory_controller/command`. Publishing must stay behind explicit safety
gates, including operator enable/deadman state, current packet freshness, joint
limit validation, safe startup posture, and emergency stop procedure.

### Filtering, Smoothing, Rate Limits, And Deadbands

Add filtering/smoothing only after raw, calibrated, mapped, and outgoing states
are separated. Rate limits, deadbands, and sudden-jump prevention should be
implemented as explicit pipeline stages with clear diagnostics.

### Closed-Loop Safety And Feedback

Later closed-loop work may use Shadow state feedback, tactile topics, controller
state, logging, neutral fallback, operator enable/disable state, and emergency
stop behavior. PID or other closed-loop control is a later safety/control phase,
not a prerequisite for the current dry-run architecture.

## Storage Recommendation

Use JSON sidecars plus a JSON registry/manifest. This gives database-like active
selection behavior while staying human-readable, recoverable by rescanning
sidecars, and simple enough for the current project. Defer SQLite until record
volume, concurrent writes, or query complexity justify it.

## Runtime Calibration Location

Default generated calibration data location:

```text
runtime_data/senseglove_r1/calibrations/
```

Backward compatibility:

- Read explicit legacy paths unchanged.
- Clear new usage is preferred; explicit paths can still be loaded when supplied.
- Do not silently move files.
- Continue reading old CSV+JSON sidecars.
- Stop writing new runtime calibration files into `docs/`.

## Deferred

- Live Shadow Hand publishing
- ROS1/ROS2 bridge
- UDP/TCP bridge
- PID or closed-loop control
- Filtering/smoothing implementation
- Abduction-to-Shadow mapping
- Full mirror-mode mapping
- Full database service
- SQLite migration
- Raw `joint_angles`-based calibration math
- Full 5-finger Shadow command mapping
