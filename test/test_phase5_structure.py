from pathlib import Path


def test_setup_uses_explicit_senseglove_r1_commands_only():
    setup_text = Path("setup.py").read_text()

    assert "senseglove_r1_calibration = r1_shadow_teleop.calibration.tool_node:main" in setup_text
    assert "senseglove_r1_listener = r1_shadow_teleop.dashboard.listener_node:main" in setup_text
    assert "senseglove_r1_calibration_printer = r1_shadow_teleop.senseglove_r1.calibration_printer:main" in setup_text
    assert "\"r1_calibration =" not in setup_text
    assert "\"r1_glove_listener =" not in setup_text
    assert "\"r1_calibration_printer =" not in setup_text


def test_runtime_calibration_directory_placeholder_is_preserved():
    path = Path("runtime_data/senseglove_r1/calibrations/.gitkeep")

    assert path.exists()


def test_shadow_hand_packet_directory_placeholder_is_preserved():
    path = Path("runtime_data/shadow_hand/.gitkeep")

    assert path.exists()


def test_shadow_hand_default_packet_path_is_runtime_data():
    from r1_shadow_teleop.shadow_hand.command_packet import DEFAULT_COMMAND_PACKET_PATH

    expected = (
        Path(__file__).resolve().parents[1]
        / "runtime_data"
        / "shadow_hand"
        / "latest_command_packet.json"
    )
    assert DEFAULT_COMMAND_PACKET_PATH == expected
