from setuptools import find_packages, setup

package_name = "r1_shadow_teleop"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Gerard Jitechian",
    maintainer_email="gerard.jitechian@gmail.com",
    description="R1 SenseGlove to Shadow Hand teleoperation research package.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "senseglove_r1_listener = r1_shadow_teleop.dashboard.listener_node:main",
            "senseglove_r1_calibration = r1_shadow_teleop.calibration.tool_node:main",
            "senseglove_r1_calibration_printer = r1_shadow_teleop.senseglove_r1.calibration_printer:main",
        ],
    },
)
