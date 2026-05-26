import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeNode:
    def __init__(self, *args, **kwargs):
        pass


fake_rclpy = types.ModuleType("rclpy")
fake_rclpy.node = types.ModuleType("rclpy.node")
fake_rclpy.node.Node = FakeNode
fake_rclpy.init = lambda *args, **kwargs: None
fake_rclpy.shutdown = lambda *args, **kwargs: None
fake_rclpy.spin = lambda *args, **kwargs: None
sys.modules.setdefault("rclpy", fake_rclpy)
sys.modules.setdefault("rclpy.node", fake_rclpy.node)

fake_r1_msgs = types.ModuleType("r1_msgs")
fake_r1_msgs.msg = types.ModuleType("r1_msgs.msg")
fake_r1_msgs.msg.R1GloveState = object
sys.modules.setdefault("r1_msgs", fake_r1_msgs)
sys.modules.setdefault("r1_msgs.msg", fake_r1_msgs.msg)

calibration_tool = importlib.import_module("r1_shadow_teleop.calibration.tool_node")
terminal_ui_module = importlib.import_module("r1_shadow_teleop.calibration.terminal_ui")
poses_module = importlib.import_module("r1_shadow_teleop.calibration.poses")
calibration_tool.run_timed_progress = terminal_ui_module.run_timed_progress
calibration_tool.flexion_poses = poses_module.flexion_poses
calibration_tool.abduction_poses = poses_module.abduction_poses
calibration_tool.pinch_validation_poses = poses_module.pinch_validation_poses


class CaptureUI:
    console = None

    def __init__(self):
        self.messages = []

    def write(self, message=""):
        self.messages.append(str(message))

    def warning(self, message):
        self.messages.append(f"warning: {message}")


def test_invalid_parsers_echo_value_and_accepted_aliases():
    for parser, bad_value, expected in (
        (calibration_tool.parse_hand, "center", "r/right"),
        (calibration_tool.parse_mode, "wave", "f/flexion"),
        (calibration_tool.parse_fingers, "pointer", "i/index"),
    ):
        try:
            parser(bad_value)
        except ValueError as exc:
            message = str(exc)
        else:
            raise AssertionError("parser accepted invalid value")
        assert bad_value in message
        assert expected in message


def test_timed_progress_zero_duration_does_not_sleep():
    ui = CaptureUI()
    sleeps = []

    calibration_tool.run_timed_progress(
        "Settling",
        0.0,
        ui,
        sleep_fn=sleeps.append,
    )

    assert sleeps == []
    assert any("Settling for 0.0s" in item for item in ui.messages)


def test_timed_progress_fallback_uses_configured_duration_once():
    ui = CaptureUI()
    sleeps = []

    calibration_tool.run_timed_progress(
        "Sampling",
        0.25,
        ui,
        sleep_fn=sleeps.append,
    )

    assert sleeps == [0.25]
    assert any("Sampling for 0.2s" in item for item in ui.messages)


def test_decision_for_pose_abort_raises(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    try:
        calibration_tool.decision_for_pose(optional=False)
    except calibration_tool.AbortCalibration:
        pass
    else:
        raise AssertionError("abort action did not raise AbortCalibration")


def test_pose_prompts_include_safety_and_anatomy_guidance():
    poses = []
    poses.extend(calibration_tool.flexion_poses(["index"]))
    poses.extend(calibration_tool.abduction_poses(["thumb", "index"]))
    poses.extend(calibration_tool.pinch_validation_poses(["index"]))

    combined = "\n".join(
        line.lower()
        for pose in poses
        for line in pose["instructions"]
    )

    assert "target" in combined
    assert "thumb" in combined
    assert "non-target" in combined
    assert "comfortable" in combined
    assert "strain" in combined
    assert "hyperextension" in combined
    assert "natural coupling" in combined
    assert "do not press hard" in combined
    assert "minimal side-to-side spread" in combined
    assert "gently together" in combined
    assert "spread side-to-side" in combined
