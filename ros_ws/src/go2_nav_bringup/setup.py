from glob import glob
from setuptools import setup

package_name = "go2_nav_bringup"

setup(
    name=package_name,
    version="0.1.0",
    packages=[],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
        (f"share/{package_name}/params", glob("params/*.yaml")),
        (f"share/{package_name}/rviz", glob("rviz/*.rviz")),
        (f"share/{package_name}/maps", glob("maps/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Go2 Robot",
    maintainer_email="devnull@example.com",
    description="Go2 navigation bringup assets for ROS 2 Foxy.",
    license="Proprietary",
)
