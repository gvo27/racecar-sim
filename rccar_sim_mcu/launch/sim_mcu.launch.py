"""Start the virtual ESP32 (node rccar_mcu). Argument: use_sim_time (default false)."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false',
                              description='Use /clock for the node.'),
        Node(package='rccar_sim_mcu', executable='rccar_mcu_sim', name='rccar_mcu',
             output='screen',
             parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}]),
    ])
