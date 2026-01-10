import numpy as np
import rclpy
import torch
from ackermann_msgs.msg import AckermannDriveStamped
from lib.model import TinyLidarNet, TinyLidarNetSmall
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class TinyLidarNetEvaluator(Node):
    def __init__(self, model_path, model_type="large", device="cpu"):
        super().__init__("tiny_lidar_net_evaluator")

        self.device = torch.device(device)
        self.model = self._load_model(model_path, model_type).to(self.device)
        self.model.eval()

        self.subscription = self.create_subscription(
            LaserScan, "/sensing/lidar/scan", self.scan_callback, 1
        )

        self.publisher = self.create_publisher(
            AckermannDriveStamped, "/control/command/control_cmd", 1
        )

        self.max_range = 30.0
        self.target_velocity = 8.0  # Default evaluation speed

        self.get_logger().info("TinyLidarNet Evaluator Initialized")

    def _load_model(self, path, model_type):
        if model_type == "small":
            model = TinyLidarNetSmall(input_dim=1080, output_dim=2)
        else:
            model = TinyLidarNet(input_dim=1080, output_dim=2)

        model.load_state_dict(torch.load(path, map_location=self.device))
        return model

    def scan_callback(self, msg):
        # Preprocess scan
        ranges = np.array(msg.ranges, dtype=np.float32)
        ranges = np.nan_to_num(ranges, posinf=self.max_range, neginf=0.0, nan=self.max_range)
        ranges = np.clip(ranges, 0.0, self.max_range) / self.max_range

        # Inference
        tensor = torch.from_numpy(ranges).unsqueeze(0).unsqueeze(1).to(self.device)

        with torch.no_grad():
            output = self.model(tensor)

        accel = output[0, 0].item()
        steer = output[0, 1].item()

        # Publish command
        cmd = AckermannDriveStamped()
        cmd.header = msg.header
        cmd.drive.steering_angle = steer
        cmd.drive.acceleration = accel
        # For evaluation, we might want to fix velocity or use model output
        # TinyLidarNet was trained to predict accel, so use it.
        # But to ensure movement, we might assume a base velocity logic if needed.
        # Here we trust the model.

        # Override speed for simplicity if model output is just accel
        # The car needs speed. The model predicts accel.
        # In simulation, we need to manage speed.
        # For now, let's just publish.
        cmd.drive.speed = self.target_velocity  # Simplified for now, or integration required

        self.publisher.publish(cmd)


def main(args=None):
    rclpy.init(args=args)

    # We need args parsing
    # But usually this is run via ros2 run or launch
    # Hardcoding defaults for now or use sys.argv

    node = TinyLidarNetEvaluator("checkpoints/tiny_lidar_net_v6_1500/best_model.pth")
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
