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
5. Package/module reorganization with compatibility wrappers
6. Shadow model/config scaffolding only
7. Future pipeline boundaries for filtering/transport, still dry-run only

## Phase 1: Runtime Paths And Backward Compatibility

**Goal:** Move generated calibration data out of `docs/` without breaking
existing files.

**Why first:** Storage location affects calibration capture, listener defaults,
docs, and tests. It should be stabilized before changing registry semantics.

**Plan:**

- Add a runtime path helper with default calibration dir:
  `r1_shadow_teleop/calibrations/`
- Keep `docs/calibrations/` as a read-only fallback search location.
- Preserve explicit legacy file loading through `calibration_csv_path`.
- New writes go to `r1_shadow_teleop/calibrations/`.
- Existing `docs/calibrations/*` files remain loadable.

**Likely changes:**

- `r1_shadow_teleop/r1_calibration.py`
- `r1_shadow_teleop/r1_calibration_tool.py`
- `r1_shadow_teleop/r1_glove_listener.py`
- README/runbook references

**Must not change in this phase:**

- Calibration math
- Pose sequence
- Shadow preview mapping
- ROS entry points

**Checks:**

- `python3 -m py_compile r1_shadow_teleop/*.py`
- `colcon build --symlink-install --packages-select r1_shadow_teleop`
- Listener can load an explicit old `docs/calibrations/*.csv`.
- Calibration tool writes a new file to
  `r1_shadow_teleop/calibrations/`.

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
  `r1_shadow_teleop/calibrations/calibration_registry.json`.

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

**Goal:** Reduce flat proof-of-concept structure while keeping ROS commands
stable.

Recommended structure:

```text
r1_shadow_teleop/
  r1_glove_listener.py
  r1_calibration_tool.py
  r1_calibration_printer.py

  config/
    runtime_paths.py
    hand_selection.py

  r1/
    frame.py
    adapter.py
    diagnostics.py

  calibration/
    models.py
    poses.py
    capture.py
    validation.py
    storage.py
    resolver.py
    terminal_ui.py

  dashboard/
    listener_node.py
    render.py
    abduction.py

  shadow/
    models.py
    mapping_preview.py
    trajectory.py
    command_packet.py

  pipeline/
    states.py
    interfaces.py
```

Top-level modules should remain thin compatibility wrappers so these commands
continue to work:

- `ros2 run r1_shadow_teleop r1_calibration`
- `ros2 run r1_shadow_teleop r1_glove_listener`

## Phase 6: Shadow Hand Model/Configuration Scaffolding

**Goal:** Represent target hand configuration without implementing control.

Add config concepts for:

- `input_hand`
- `target_hand`
- `shadow_hand_model`
- `mirror_mode`

Known model names should include `hand_lite_3finger` and
`hand_full_5finger`. Current mapping remains a dry-run preview.

## Phase 7: Future Pipeline Boundaries Only

**Goal:** Prepare clean internal state boundaries for later filtering, mapping,
and transport.

Define lightweight interfaces for:

- raw glove state
- calibrated glove state
- mapped Shadow target state
- filtered target state
- outgoing command packet/trajectory

Do not implement filtering, PID, networking, bridges, or live publishing in this
phase.

## Storage Recommendation

Use JSON sidecars plus a JSON registry/manifest. This gives database-like active
selection behavior while staying human-readable, recoverable by rescanning
sidecars, and simple enough for the current project. Defer SQLite until record
volume, concurrent writes, or query complexity justify it.

## Runtime Calibration Location

Default new runtime location:

```text
r1_shadow_teleop/calibrations/
```

Backward compatibility:

- Read explicit legacy paths unchanged.
- If no records exist in the new location, scan `docs/calibrations/`.
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
