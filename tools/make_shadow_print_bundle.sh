#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$HOME/shadow_print_only_bundle_${STAMP}"
OUT_TAR="$HOME/shadow_print_only_bundle_${STAMP}.tar.gz"

mkdir -p "$OUT_DIR/r1_shadow_teleop/tools"
mkdir -p "$OUT_DIR/r1_shadow_teleop/docs"
mkdir -p "$OUT_DIR/r1_shadow_teleop/runtime_data/shadow_hand"

cp "$REPO_DIR/tools/shadow_ros1_sender.py" "$OUT_DIR/r1_shadow_teleop/tools/"
cp "$REPO_DIR/tools/shadow_print_receiver.py" "$OUT_DIR/r1_shadow_teleop/tools/" 2>/dev/null || true
cp "$REPO_DIR/docs/shadow_ros1_sender_safety.md" "$OUT_DIR/r1_shadow_teleop/docs/" 2>/dev/null || true

if [ -f "$REPO_DIR/runtime_data/shadow_hand/latest_command_packet.json" ]; then
  cp "$REPO_DIR/runtime_data/shadow_hand/latest_command_packet.json" "$OUT_DIR/r1_shadow_teleop/runtime_data/shadow_hand/"
else
  echo "ERROR: runtime_data/shadow_hand/latest_command_packet.json not found."
  echo "Run senseglove_r1_listener first so it generates a packet."
  exit 1
fi

cat > "$OUT_DIR/r1_shadow_teleop/README_SHADOW_PRINT_ONLY.txt" <<'README'
Shadow print-only test bundle

This bundle is for validating the Shadow-side command shape only.

It does not publish unless explicitly run with publishing flags, and the included packet should still refuse publishing because:
- safety.publish_to_robot is false
- safety.dry_run_only is true

One-shot print-only test:
  cd r1_shadow_teleop
  python3 tools/shadow_ros1_sender.py --packet runtime_data/shadow_hand/latest_command_packet.json

Safety refusal test:
  python3 tools/shadow_ros1_sender.py --packet runtime_data/shadow_hand/latest_command_packet.json --publish --i-understand-this-can-move-the-robot
README

tar -czf "$OUT_TAR" -C "$OUT_DIR" .

echo "Created:"
echo "$OUT_TAR"
ls -lh "$OUT_TAR"
