"""ROS 2 transport only. The policy sees the documented sensor allowlist."""
import gc
import json
import time
import sys
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger
from him_safety_interfaces.msg import RobotFeedback, JointCommand, Abort
from policy.controller import Controller


class TouchNode(Node):
    def __init__(self, controller):
        super().__init__('right_hand_rule')
        self.controller = controller
        self.session = None
        self.sequence = 0
        self.sent = -1
        self.done = False
        self.feedback, self.imu = {}, {}
        qos = QoSProfile(depth=16, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.publisher = self.create_publisher(JointCommand, '/safety/precheck',
                                               QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE))
        self.create_subscription(RobotFeedback, '/safety/policy_observation', self.on_feedback, qos)
        self.create_subscription(String, '/safety/policy_state', self.on_state, qos)
        self.create_subscription(Abort, '/safety/abort', self.on_abort,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.arm = self.create_client(Trigger, '/safety/checker/arm')

    def on_abort(self, message):
        self.done = True
        self.get_logger().error('Checker abort: ' + message.reason)

    @staticmethod
    def trim(cache):
        while len(cache) > 16:
            del cache[next(iter(cache))]

    def on_feedback(self, message):
        key = int(message.observation_id)
        self.feedback[key] = (time.monotonic(), list(message.q), list(message.dq))
        self.trim(self.feedback)
        self.maybe_send(key)

    def on_state(self, message):
        try:
            raw = json.loads(message.data)
            key = int(raw['observation_id'])
            # Privileged JSON fields never enter either cache or the controller.
            self.imu[key] = (time.monotonic(), raw['quat'], raw['gyro'], raw.get('control_ready') is True)
            self.trim(self.imu)
            self.maybe_send(key)
        except (ValueError, KeyError, TypeError):
            return

    def maybe_send(self, key):
        if self.done or not self.session or key <= self.sent or key not in self.feedback or key not in self.imu:
            return
        stamp_q, q, dq = self.feedback[key]
        stamp_imu, quat, gyro, ready = self.imu[key]
        if time.monotonic()-min(stamp_q, stamp_imu) > .12:
            return
        try:
            result = self.controller.act(dict(q=q, dq=dq, quat=quat, gyro=gyro), ready=ready)
            message = JointCommand()
            message.session_id = self.session
            message.sequence = self.sequence
            message.observation_id = key
            for field in ('q','dq','kp','kd','tau'):
                values = np.asarray(result[field], dtype=float)
                if values.shape != (29,) or not np.isfinite(values).all():
                    raise ValueError('Invalid actuator command')
                setattr(message, field, values.tolist())
            self.publisher.publish(message)
            self.sent = key
            self.sequence += 1
        except Exception as exc:
            self.done = True
            self.get_logger().error('Policy stopped: ' + str(exc))

    def start(self):
        if not self.arm.wait_for_service(timeout_sec=15.):
            return False
        future = self.arm.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.)
        result = future.result()
        if result is None or not result.success or not result.message:
            return False
        self.session = result.message
        return True


def main():
    controller = Controller()
    rclpy.init()
    node = TouchNode(controller)
    gc.disable()
    try:
        if not node.start():
            return 2
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=.02)
    finally:
        node.destroy_node()
        rclpy.shutdown()
        gc.enable()
        gc.collect()
    return 0


if __name__ == '__main__':
    sys.exit(main())
