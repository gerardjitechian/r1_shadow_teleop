# R1 to Shadow Mapping Notes

Current status:
- The listener subscribes to the right R1 glove topic:
  - `/r1/glove69/rh/glove_states`
- The useful R1 field is:
  - `normalized_finger_positions`
- The message definition says this field is ordered as:
  - flexion_thumb
  - flexion_index
  - flexion_middle
  - flexion_ring
  - flexion_pinky
  - abduction_thumb
  - abduction_index
  - abduction_middle
  - abduction_ring
  - abduction_pinky
- The documented range is 0 to 10000, so the first-pass code divides by 10000 to get approximate 0.0 to 1.0 flexion values.

Current mapping:
- R1 thumb maps to Shadow thumb joints.
- R1 index maps to Shadow first finger joints.
- R1 ring maps to Shadow ring finger joints.
- R1 middle and pinky are ignored for now because the Shadow Hand Lite has fewer fingers.

Important:
- This is a dry-run mapping only.
- It prints proposed Shadow targets but does not publish commands to the robot.
- Scaling, calibration, inversion, offsets, and joint limits still need to be validated before commanding hardware.

Roadmap status:
- Phase 6 adds dry-run config metadata for `input_source`, `input_hand`, `target_hand`, `shadow_hand_model`, and `mirror_mode`.
- The only supported input source is still `senseglove_r1`; future input adapters should plug in before mapping rather than inside Shadow Hand target config.
- The current mapping remains a placeholder-grade dry-run preview for the `hand_lite_3finger`-style thumb/first/ring setup.
- Future mapping should become model/config-driven rather than hardcoded.
- Mapping profiles should account for `hand_lite_3finger`, `hand_full_5finger`, target hand side, possible mirror mode, validated joint order, and verified joint limits.
- Do not use this mapping for live Shadow publishing until those validation steps exist.

The active roadmap for replacing this placeholder mapping is `docs/current_roadmap.md`.
