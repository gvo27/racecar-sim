"""ROS node of the virtual ESP32. All logic is in McuModel. This file only wires topics."""
from rcl_interfaces.msg import ParameterDescriptor
import rccar_msgs.msg as rm
from rccar_msgs.srv import McuCommand
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Range
from std_srvs.srv import Trigger

from rccar_sim_mcu.model import McuModel

DRIVE_TOPIC = '/rccar/mcu/drive'
COMMAND_TOPIC = '/rccar/mcu/command'
EVENT_TOPIC = '/rccar/mcu/event'
TELEMETRY_TOPIC = '/rccar/mcu/telemetry'
RANGE_TOPIC = '/rccar/rangefinder/range'
RANGE_FRAME = 'rangefinder_link'

BEST_EFFORT_1 = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
SENSOR_QOS = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)
EVENT_QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class RccarMcu(Node):
    """Virtual ESP32. It subscribes to the drive topic. It never publishes it."""

    def __init__(self):
        super().__init__('rccar_mcu')
        self.declare_parameter(
            'fault_drop_ms', 1000,
            ParameterDescriptor(
                description='Fault drop_drive. Ignore drive messages for this many ms.'))
        # The model clock is ms since boot, like esp_timer on the firmware.
        self._boot_ms = self._now_ms()
        self._model = McuModel(0)
        self._drop_until_ms = -1

        self.create_subscription(rm.DriveCmd, DRIVE_TOPIC, self._on_drive, BEST_EFFORT_1)
        self.create_service(McuCommand, COMMAND_TOPIC, self._on_command)
        self._event_pub = self.create_publisher(rm.McuEvent, EVENT_TOPIC, EVENT_QOS)
        self._tel_pub = self.create_publisher(rm.Telemetry, TELEMETRY_TOPIC, SENSOR_QOS)
        self._range_pub = self.create_publisher(Range, RANGE_TOPIC, SENSOR_QOS)
        # Sim-only fault services. They stay in the private namespace.
        self.create_service(Trigger, '~/fault_drop_drive', self._on_fault_drop)
        self.create_service(Trigger, '~/fault_reboot', self._on_fault_reboot)

        self._control_timer = None
        self._control_hz = 0
        self._tel_timer = None
        self._tel_hz = -1
        self._range_timer = None
        self._range_ms = 0
        self._retime()
        self.create_timer(0.05, self._retime)  # picks up SET control_hz, TEL and rf_period_ms
        # READY goes out on the first tick. The bridge may miss it (volatile). The bridge also
        # pushes tuning from its startup timer (bridge_node.py:179), like the firmware on connect.
        self.get_logger().info('virtual ESP32 up: disarmed, READY queued')

    # -- time ---------------------------------------------------------------
    def _now_ms(self) -> int:
        return self.get_clock().now().nanoseconds // 1_000_000

    def _mcu_ms(self) -> int:
        return self._now_ms() - self._boot_ms

    def _stamp(self):
        return self.get_clock().now().to_msg()

    # -- timers -------------------------------------------------------------
    def _retime(self):
        m = self._model
        if m.cfg.control_hz != self._control_hz:
            if self._control_timer is not None:
                self.destroy_timer(self._control_timer)
            self._control_hz = m.cfg.control_hz
            self._control_timer = self.create_timer(1.0 / self._control_hz, self._on_control)
        if m.telemetry_hz != self._tel_hz:
            if self._tel_timer is not None:
                self.destroy_timer(self._tel_timer)
                self._tel_timer = None
            self._tel_hz = m.telemetry_hz
            if self._tel_hz > 0:
                self._tel_timer = self.create_timer(1.0 / self._tel_hz, self._on_telemetry)
        if m.cfg.rf_period_ms != self._range_ms:
            if self._range_timer is not None:
                self.destroy_timer(self._range_timer)
                self._range_timer = None
            self._range_ms = m.cfg.rf_period_ms
            if self._range_ms > 0:
                self._range_timer = self.create_timer(self._range_ms / 1000.0, self._on_range)

    def _on_control(self):
        self._model.step(self._mcu_ms())
        self._publish_events()

    def _publish_events(self):
        for code, text in self._model.pop_events():
            msg = rm.McuEvent()
            msg.stamp = self._stamp()
            msg.code = code
            msg.text = text[:64]
            self._event_pub.publish(msg)

    def _on_telemetry(self):
        t = self._model.telemetry(self._mcu_ms())
        msg = rm.Telemetry()
        msg.stamp = self._stamp() if t.time_synced else msg.stamp
        msg.mcu_ms = t.mcu_ms
        msg.heading_rad = t.heading_rad
        msg.throttle = t.throttle
        msg.steer_rad = t.steer_rad
        msg.steer_us = t.steer_us
        msg.throttle_us = t.throttle_us
        msg.armed = t.armed
        msg.time_synced = t.time_synced
        self._tel_pub.publish(msg)

    def _on_range(self):
        cfg = self._model.cfg
        msg = Range()
        msg.header.stamp = self._stamp()
        msg.header.frame_id = RANGE_FRAME
        msg.radiation_type = cfg.rf_radiation
        msg.field_of_view = float(cfg.rf_fov_rad)
        msg.min_range = float(cfg.rf_min_m)
        msg.max_range = float(cfg.rf_max_m)
        msg.range = float(self._model.range_m())
        self._range_pub.publish(msg)

    # -- inputs -------------------------------------------------------------
    def _on_drive(self, msg):
        now = self._mcu_ms()
        if now < self._drop_until_ms:
            return
        self._model.on_drive(msg.heading_rad, msg.throttle, now)

    def _on_command(self, request, response):
        response.ok, response.reply = self._model.service_command(request.command, self._mcu_ms())
        self._retime()
        self._publish_events()
        return response

    def _on_fault_drop(self, request, response):
        ms = int(self.get_parameter('fault_drop_ms').value)
        self._drop_until_ms = self._mcu_ms() + ms
        response.success = True
        response.message = f'dropping drive messages for {ms} ms'
        self.get_logger().warning(response.message)
        return response

    def _on_fault_reboot(self, request, response):
        self._boot_ms = self._now_ms()  # esp_timer restarts at boot
        self._model.reboot(0)
        self._drop_until_ms = -1
        self._retime()
        self._publish_events()
        response.success = True
        response.message = 'rebooted'
        self.get_logger().warning('fault: reboot')
        return response


def main(args=None):
    rclpy.init(args=args)
    node = RccarMcu()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
