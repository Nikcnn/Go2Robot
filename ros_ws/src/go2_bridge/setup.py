from setuptools import find_packages, setup

package_name = "go2_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Go2 Robot",
    maintainer_email="devnull@example.com",
    description="Go2 ROS 2 bridge nodes.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "base_bridge = go2_bridge.base_bridge:main",
            "camera_bridge = go2_bridge.camera_bridge:main",
            "lidar_bridge = go2_bridge.lidar_bridge:main",
        ],
    },
)
