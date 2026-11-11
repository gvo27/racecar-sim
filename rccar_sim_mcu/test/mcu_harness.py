"""Shared helpers for the launch tests. The test node acts as a teleop (publishes admin)."""
import os
import time

from rccar_msgs.msg import DriveCmd, McuEvent, SupervisorState, Telemetry
from rccar_msgs.srv import McuCommand, Reset
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_srvs.srv import Trigger

RACECAR = os.environ.get('RACECAR_SRC', '/ws/src/racecar')
TUNING = os.path.join(RACECAR, 'tuning.toml')
SEND_HZ = 20.0
STATE_QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.TRANSIENT_LOCAL)


class Harness:
    """A test node with spin helpers, event log, telemetry and service clients."""

    def __init__(self, name):
        self.node = rclpy.create_node(name)
        n = self.node
        self.events, self.state, self.tel = [], None, None
        self.admin = n.create_publisher(
            DriveCmd, '/rccar/cmd/admin',
            QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE))
        n.create_subscription(McuEvent, '/rccar/mcu/event',
                              lambda m: self.events.append(m.code),
                              QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE))
        n.create_subscription(Telemetry, '/rccar/mcu/telemetry', self._on_tel,
                              QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
        n.create_subscription(SupervisorState, '/rccar/supervisor/state', self._on_state,
                              STATE_QOS)
        self.cmd_cli = n.create_client(McuCommand, '/rccar/mcu/command')
        self.arm_cli = n.create_client(Reset, '/supervisor/arm')
        self.drop_cli = n.create_client(Trigger, '/rccar_mcu/fault_drop_drive')
        self.reboot_cli = n.create_client(Trigger, '/rccar_mcu/fault_reboot')
        self._next_pub = 0.0

    def _on_tel(self, msg):
        self.tel = msg

    def _on_state(self, msg):
        self.state = msg

    def spin(self, seconds, neutral=False):
        """Spin. With neutral, publish neutral admin commands at SEND_HZ."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if neutral and time.monotonic() >= self._next_pub:
                msg = DriveCmd()
                msg.source = 'test'
                self.admin.publish(msg)
                self._next_pub = time.monotonic() + 1.0 / SEND_HZ
            rclpy.spin_once(self.node, timeout_sec=0.01)

    def wait_for(self, cond, timeout=30.0, neutral=False):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if cond():
                return True
            self.spin(0.05, neutral)
        return cond()

    def call(self, client, request, timeout=10.0, neutral=False):
        future = client.call_async(request)
        end = time.monotonic() + timeout
        while not future.done() and time.monotonic() < end:
            self.spin(0.02, neutral)
        return future.result() if future.done() else None

    def get(self):
        """GET over the command service. Return the reply text or ''."""
        req = McuCommand.Request()
        req.command = 'GET'
        res = self.call(self.cmd_cli, req, timeout=3.0)
        return res.reply if res is not None else ''

    def tuning_pushed(self):
        r = self.get()
        return ('maxdeg=30.0' in r and 'gain=2.00' in r and 'limit=0.70' in r
                and 'left=1200' in r and 'right=1800' in r)

    def arm(self):
        """Neutral admin, then Reset with the current incident. Return the response."""
        self.events.clear()
        self.spin(1.0, neutral=True)
        req = Reset.Request()
        req.incident = self.state.incident
        return self.call(self.arm_cli, req, neutral=True)
