# R1 Calibration Plan

Goal:
Determine how R1 normalized_finger_positions behaves for the right glove before commanding the Shadow Hand.

We need to confirm:

- Which R1 value changes for each physical finger.
- Whether open hand is low or high.
- Whether closed hand is low or high.
- Whether values need inversion.
- Approximate min/max values for each relevant finger.
- Which R1 fingers should map to the Shadow Hand Lite fingers.

R1 field:
`normalized_finger_positions`

Message definition order:
1. flexion_thumb
2. flexion_index
3. flexion_middle
4. flexion_ring
5. flexion_pinky
6. abduction_thumb
7. abduction_index
8. abduction_middle
9. abduction_ring
10. abduction_pinky

Current first-pass mapping:

- R1 thumb -> Shadow thumb
- R1 index -> Shadow first finger
- R1 ring -> Shadow ring finger
- R1 middle ignored
- R1 pinky ignored

Calibration poses to test:

1. Open relaxed hand
2. Full fist
3. Thumb flex only
4. Index flex only
5. Middle flex only
6. Ring flex only
7. Pinky flex only
8. Index-thumb pinch
9. Ring-thumb pinch

Notes:
- Current code only prints proposed targets.
- It does not publish commands to Shadow Hand.
- Calibration must be completed before commanding hardware.
