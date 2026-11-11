"""launch_testing: arm, drop-drive FAILSAFE, reboot, with the car supervisor and bridge."""
import os
import tempfile
import unittest

from ament_index_python.packages import get_package_share_directory
import launch
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import launch_testing.actions
import pytest
from rccar_msgs.msg import McuEvent
import rclpy
from std_srvs.srv import Trigger

from mcu_harness import Harness, TUNING


@pytest.mark.launch_test
def generate_test_description():
    car = os.path.join(get_package_share_directory('rccar_bringup'), 'launch', 'car.launch.py')
    return launch.LaunchDescription([
        Node(package='rccar_sim_mcu', executable='rccar_mcu_sim', name='rccar_mcu',
             output='screen', parameters=[{'fault_drop_ms': 1500}]),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(car),
            launch_arguments={'sim': 'true', 'use_sim_time': 'false',
                              'tuning_file': TUNING,
                              'heartbeat_dir': tempfile.mkdtemp()}.items()),
        launch_testing.actions.ReadyToTest(),
    ])


class TestFailsafe(unittest.TestCase):
    """Cases run in name order (a_, b_). The second case needs the first one done."""

    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.h = Harness('failsafe_test')

    @classmethod
    def tearDownClass(cls):
        cls.h.node.destroy_node()
        rclpy.shutdown()

    def _ready(self):
        h = self.h
        self.assertTrue(h.cmd_cli.wait_for_service(30.0))
        self.assertTrue(h.arm_cli.wait_for_service(30.0))
        self.assertTrue(h.drop_cli.wait_for_service(30.0))
        self.assertTrue(h.wait_for(lambda: h.state is not None, neutral=True), 'no state')
        self.assertTrue(h.wait_for(h.tuning_pushed, timeout=60.0, neutral=True),
                        'tuning not pushed')

    def _arm(self):
        h = self.h
        res = h.arm()
        self.assertIsNotNone(res, 'arm call timed out')
        self.assertTrue(res.ok, res.message)
        self.assertTrue(h.wait_for(lambda: h.tel is not None and h.tel.armed, neutral=True),
                        'MCU not armed')
        self.assertIn(McuEvent.ARMED, h.events)

    def test_a_drop_drive_failsafe(self):
        h = self.h
        self._ready()
        self._arm()
        incident = h.state.incident
        h.events.clear()
        res = h.call(h.drop_cli, Trigger.Request(), neutral=True)
        self.assertTrue(res is not None and res.success)
        self.assertTrue(h.wait_for(lambda: McuEvent.DISARMED in h.events, timeout=15.0,
                                   neutral=True), f'events {h.events}')
        self.assertLess(h.events.index(McuEvent.FAILSAFE), h.events.index(McuEvent.DISARMED))
        self.assertTrue(h.wait_for(lambda: h.state.estop_latched, neutral=True))
        self.assertGreater(h.state.incident, incident)

    def test_b_reboot_latches_and_repushes_tuning(self):
        h = self.h
        self._ready()
        # wait until the drop window of case a ends, then re-arm with the new incident
        h.spin(2.0, neutral=True)
        self._arm()
        incident = h.state.incident
        h.events.clear()
        res = h.call(h.reboot_cli, Trigger.Request(), neutral=True)
        self.assertTrue(res is not None and res.success)
        self.assertTrue(h.wait_for(lambda: McuEvent.READY in h.events, neutral=True))
        self.assertTrue(h.wait_for(lambda: h.state.estop_latched, neutral=True))
        self.assertIn('reboot', h.state.reason)
        self.assertGreater(h.state.incident, incident)
        self.assertTrue(h.wait_for(h.tuning_pushed, timeout=60.0, neutral=True),
                        f'no re-push, last GET: {h.get()}')
