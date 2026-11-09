FROM ros:foxy-ros-base
SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake python3-pip python3-colcon-common-extensions \
    ros-foxy-rosidl-default-generators ros-foxy-rmw-fastrtps-cpp ros-foxy-std-srvs \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir numpy==1.24.4
WORKDIR /submission
COPY vendor/builder-kit/ros2/him_safety_interfaces interfaces
RUN source /opt/ros/foxy/setup.bash && colcon build --base-paths interfaces --packages-select him_safety_interfaces
COPY policy policy
COPY container/ros_node.py container/entrypoint.sh ./
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["/bin/bash", "/submission/entrypoint.sh"]
