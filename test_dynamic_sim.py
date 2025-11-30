"""Test dynamic simulator behavior."""

from simulator_dynamic import DynamicSimulator

from core.data import Action, VehicleState

# 初期状態を設定
initial_state = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=5.0)
sim = DynamicSimulator(initial_state=initial_state, dt=0.01)
sim.reset()

print("=" * 80)
print("Dynamic Simulator Test: Straight line with constant velocity")
print("=" * 80)
print(
    f"{'Step':>6} | {'Time':>6} | {'X':>8} | {'Y':>8} | {'Yaw':>8} | {'Vx':>8} | {'Vy':>8} | {'V':>8}"
)
print("-" * 80)

# 100ステップ実行(1秒分)
for i in range(0, 101, 10):
    if i > 0:
        for _ in range(10):
            action = Action(steering=0.0, acceleration=0.0)  # 等速直線運動
            state, _, _, _ = sim.step(action)
    else:
        state = sim._current_state  # noqa: SLF001

    dyn_state = sim._dynamic_state  # noqa: SLF001
    print(
        f"{i:6d} | {i*0.01:6.2f} | {state.x:8.3f} | {state.y:8.3f} | "
        f"{state.yaw:8.3f} | {dyn_state.vx:8.3f} | {dyn_state.vy:8.3f} | {state.velocity:8.3f}"
    )

print("\n" + "=" * 80)
print("Dynamic Simulator Test: Turning with steering")
print("=" * 80)

# リセット
sim.reset()
print(
    f"{'Step':>6} | {'Time':>6} | {'X':>8} | {'Y':>8} | {'Yaw':>8} | {'Vx':>8} | {'Vy':>8} | {'V':>8}"
)
print("-" * 80)

# ステアリングを加えて旋回
for i in range(0, 101, 10):
    if i > 0:
        for _ in range(10):
            action = Action(steering=0.1, acceleration=0.0)  # 左旋回
            state, _, _, _ = sim.step(action)
    else:
        state = sim._current_state  # noqa: SLF001

    dyn_state = sim._dynamic_state  # noqa: SLF001
    print(
        f"{i:6d} | {i*0.01:6.2f} | {state.x:8.3f} | {state.y:8.3f} | "
        f"{state.yaw:8.3f} | {dyn_state.vx:8.3f} | {dyn_state.vy:8.3f} | {state.velocity:8.3f}"
    )

print("\n" + "=" * 80)
print("Dynamic Simulator Test: Acceleration from standstill")
print("=" * 80)

# 停止状態から加速
initial_state = VehicleState(x=0.0, y=0.0, yaw=0.0, velocity=0.0)
sim = DynamicSimulator(initial_state=initial_state, dt=0.01)
sim.reset()

print(
    f"{'Step':>6} | {'Time':>6} | {'X':>8} | {'Y':>8} | {'Yaw':>8} | {'Vx':>8} | {'Vy':>8} | {'V':>8}"
)
print("-" * 80)

for i in range(0, 501, 50):
    if i > 0:
        for _ in range(50):
            action = Action(steering=0.0, acceleration=5.0)  # 強い加速
            state, _, _, _ = sim.step(action)
    else:
        state = sim._current_state  # noqa: SLF001

    dyn_state = sim._dynamic_state  # noqa: SLF001
    print(
        f"{i:6d} | {i*0.01:6.2f} | {state.x:8.3f} | {state.y:8.3f} | "
        f"{state.yaw:8.3f} | {dyn_state.vx:8.3f} | {dyn_state.vy:8.3f} | {state.velocity:8.3f}"
    )

print("\n" + "=" * 80)
print("Test completed!")
print("=" * 80)
