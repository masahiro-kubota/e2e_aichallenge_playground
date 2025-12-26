from ideal_sensor.sensor_node import IdealSensorConfig, IdealSensorNode


def test_ideal_sensor_node_instantiation() -> None:
    """Configオブジェクトを直接生成してIdealSensorNodeが正しくインスタンス化できるかテスト"""

    # Configの生成
    config = IdealSensorConfig()

    # ノードのインスタンス化
    node = IdealSensorNode(config=config, rate_hz=50.0)

    assert node.name == "Sensor"
