from setuptools import find_packages, setup

package_name = "go2_mission"

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
    description="Go2 ROS 2 mission nodes.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "mission_executor = go2_mission.mission_executor:main",
            "mission_api_node = go2_mission.mission_api_node:main",
        ],
    },
)
