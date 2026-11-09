#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/foxy/setup.bash
source /submission/install/setup.bash
set -u
cd /submission
exec python3 -u /submission/ros_node.py
