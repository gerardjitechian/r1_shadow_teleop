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
