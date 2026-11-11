"""launch_testing: the car bridge pushes tuning.toml to the virtual ESP32. Never arms."""
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
import rclpy

from mcu_harness import Harness, TUNING


@pytest.mark.launch_test
def generate_test_description():
    car = os.path.join(get_package_share_directory('rccar_bringup'), 'launch', 'car.launch.py')
    return launch.LaunchDescription([
        Node(package='rccar_sim_mcu', executable='rccar_mcu_sim', name='rccar_mcu',
             output='screen'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(car),
            launch_arguments={'sim': 'true', 'use_sim_time': 'false',
                              'tuning_file': TUNING,
                              'heartbeat_dir': tempfile.mkdtemp()}.items()),
        launch_testing.actions.ReadyToTest(),
    ])


class TestTuningPush(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()
        cls.h = Harness('tuning_push_test')

    @classmethod
    def tearDownClass(cls):
        cls.h.node.destroy_node()
        rclpy.shutdown()

    def test_tuning_pushed_and_never_armed(self):
        h = self.h
        self.assertTrue(h.cmd_cli.wait_for_service(30.0), 'no command service')
        self.assertTrue(h.wait_for(h.tuning_pushed, timeout=60.0),
                        f'tuning not pushed, last GET: {h.get()}')
        self.assertTrue(h.wait_for(lambda: h.tel is not None, timeout=10.0), 'no telemetry')
        h.spin(1.5)
        self.assertFalse(h.tel.armed, 'bridge must never arm')
        self.assertTrue(h.tel.time_synced)

    def test_only_supervisor_publishes_drive(self):
        h = self.h
        self.assertTrue(h.wait_for(
            lambda: len(h.node.get_publishers_info_by_topic('/rccar/mcu/drive')) > 0,
            timeout=30.0), 'no drive publisher')
        names = {i.node_name for i in h.node.get_publishers_info_by_topic('/rccar/mcu/drive')}
        self.assertEqual(names, {'supervisor'})
