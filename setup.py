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
            "r1_glove_listener = r1_shadow_teleop.r1_glove_listener:main",
            "r1_pose_recorder = r1_shadow_teleop.r1_pose_recorder:main",
            "r1_calibration_printer = r1_shadow_teleop.r1_calibration_printer:main",
        ],
    },
)
