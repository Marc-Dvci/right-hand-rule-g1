FROM ros:foxy-ros-base
SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake python3-colcon-common-extensions \
    ros-foxy-rosidl-default-generators ros-foxy-rmw-fastrtps-cpp ros-foxy-std-srvs \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /submission
COPY ros2/him_safety_interfaces /submission/interfaces
RUN source /opt/ros/foxy/setup.bash && colcon build --base-paths interfaces --packages-select him_safety_interfaces
COPY template/policy.py template/entrypoint.sh /submission/
ENTRYPOINT ["/bin/bash", "/submission/entrypoint.sh"]
