# パフォーマンス最適化計画

シミュレーターとエクスペリメントモジュールにおける、NumPy配列化とNumba JITコンパイルによる高速化の実装計画書

**作成日**: 2025-12-26
**対象バージョン**: main branch

---

## 📋 目次

1. [概要](#概要)
2. [既存の最適化](#既存の最適化)
3. [Numba JIT高速化の候補](#numba-jit高速化の候補)
4. [NumPy配列化による高速化の候補](#numpy配列化による高速化の候補)
5. [実装優先順位](#実装優先順位)
6. [実装時の注意点](#実装時の注意点)

---

## 概要

本ドキュメントは、シミュレーションパフォーマンスを向上させるための最適化候補箇所を特定し、実装計画を示すものです。

### 最適化の目的

- シミュレーション実行時間の短縮
- 大規模実験（多数のエピソード、長時間シミュレーション）の効率化
- 障害物数やウェイポイント数が多い場合のスケーラビリティ向上

---

## 既存の最適化

### ✅ LidarSensor (`simulator/src/simulator/sensor.py`)

**実装済み**: `_numba_intersection_kernel` (L219-288)

```python
@jit(nopython=True, cache=True)
def _numba_intersection_kernel(
    sensor_pos: np.ndarray,
    ray_dirs: np.ndarray,
    segments: np.ndarray,
    ranges: np.ndarray,
    range_min: float,
    range_max: float,
) -> np.ndarray:
    # レイとセグメントの交差判定をJITコンパイル
    ...
```

**効果**: LiDARスキャン処理が大幅に高速化済み

---

## Numba JIT高速化の候補

### 🔥 優先度: 高

#### 1. 障害物軌道補間 (`simulator/src/simulator/obstacle.py`)

**対象関数**: `get_obstacle_state` (L84-212)

**現状の問題**:
```python
# L144-169: ウェイポイント検索と線形補間のループ
for i in range(len(waypoints) - 1):
    if waypoints[i].time <= normalized_time <= waypoints[i + 1].time:
        # 線形補間計算
        x = wp1.x + alpha * (wp2.x - wp1.x)
        y = wp1.y + alpha * (wp2.y - wp1.y)
        ...
```

**改善案**:
- ウェイポイントをNumPy配列に変換: `times[N]`, `positions[N, 2]`, `yaws[N]`
- `np.searchsorted`で二分探索を実装
- 補間処理をNumba JIT化

**期待効果**:
- 動的障害物が多い場合: 中〜高
- ウェイポイント数が50+の場合: 高

**実装難易度**: 中

---

#### 2. 車両運動モデル更新 (`simulator/src/simulator/dynamics.py`)

**対象関数**: `update_bicycle_model` (L15-88)

**現状**:
```python
def update_bicycle_model(state, steering, acceleration, dt, wheelbase):
    # 三角関数と算術演算
    vx_next = state.vx + acceleration * dt
    x_next = state.x + vx_avg * math.cos(state.yaw) * dt
    ...
```

**改善案**:
- 関数全体をNumba JIT化
- `SimulationVehicleState`をNumPy配列またはNumba structに変換

**期待効果**:
- ステップ数が10,000以上の場合: 低〜中
- 単一車両なので効果は限定的

**実装難易度**: 低

---

### ⭐ 優先度: 中

#### 3. Simulator障害物ループ (`simulator/src/simulator/simulator.py`)

**対象箇所**: `on_run` メソッド (L132-231)

**現状の問題**:
```python
# L185-190: 障害物状態取得ループ
for obstacle in self.obstacle_manager.obstacles:
    obstacle_states.append(get_obstacle_state(obstacle, self.current_time))

# L195-199: 衝突判定ループ
for obstacle, obs_state in zip(...):
    obstacle_polygon = get_obstacle_polygon(obstacle, obs_state)
    if check_collision(poly, obstacle_polygon):
        ...
```

**改善案**:
- 障害物状態計算のベクトル化
- Shapely Polygonの代わりに純粋なNumPy配列で衝突判定

**期待効果**:
- 障害物数が10個以上の場合: 高

**実装難易度**: 高（Shapelyとの統合が困難）

---

## NumPy配列化による高速化の候補

### 🔥 優先度: 高

#### 1. 障害物状態リスト構築 (`simulator/src/simulator/simulator.py`)

**対象箇所**: L180-190

**現状**:
```python
obstacle_states = []
for obstacle in self.obstacle_manager.obstacles:
    try:
        obstacle_states.append(get_obstacle_state(obstacle, self.current_time))
    except Exception:
        continue
```

**改善案**:
- 障害物位置情報を事前にNumPy配列化: `(N_obstacles, 3)` → `[x, y, yaw]`
- ベクトル化された補間処理で一括計算

**期待効果**: 障害物数が10個以上で顕著

**実装難易度**: 中

---

#### 2. ObstacleGenerator センターライン計算 (`experiment/src/experiment/engine/obstacle_generator.py`)

**対象箇所**: L75-92

**現状**:
```python
for i in range(n_points):
    lx, ly = left_points[i]
    rx, ry = right_points[i]
    cx, cy = (lx + rx) / 2.0, (ly + ry) / 2.0
    # yaw計算
    ...
    centerline.append((cx, cy, yaw))
```

**改善案**:
```python
left = np.array(left_points)   # (N, 2)
right = np.array(right_points) # (N, 2)
center = (left + right) / 2.0  # ベクトル化

# yaw計算もベクトル化
diffs = np.diff(center, axis=0)
yaws = np.arctan2(diffs[:, 1], diffs[:, 0])
```

**期待効果**: レーンレット数×ポイント数が大きい場合に効果的

**実装難易度**: 低

---

### ⭐ 優先度: 中

#### 3. Dashboard ダウンサンプリング (`dashboard/src/dashboard/generator.py`)

**対象箇所**: L29-35

**現状**:
```python
indices = [int(i * step_size) for i in range(max_steps)]
return [steps_data[i] for i in indices]
```

**改善案**:
```python
indices = np.linspace(0, len(steps_data)-1, max_steps, dtype=int)
return [steps_data[i] for i in indices]
```

**期待効果**: ステップ数が10,000以上で小〜中程度

**実装難易度**: 低

---

#### 4. 車両/障害物ポリゴン生成

**対象ファイル**:
- `simulator/src/simulator/dynamics.py` (L124-131)
- `simulator/src/simulator/obstacle.py` (L259-265)

**現状**:
```python
points = []
for px, py in [p1, p2, p3, p4]:
    rx = px * cos_yaw - py * sin_yaw
    ry = px * sin_yaw + py * cos_yaw
    points.append((rx + x, ry + y))
```

**改善案**:
```python
corners = np.array([p1, p2, p3, p4])  # (4, 2)
rotation_matrix = np.array([[cos_yaw, -sin_yaw],
                            [sin_yaw, cos_yaw]])
rotated = corners @ rotation_matrix.T
translated = rotated + np.array([x, y])
```

**期待効果**: 呼び出し頻度が非常に高い場合のみ

**実装難易度**: 低

---

#### 5. ObstacleGenerator セグメント長計算 (`experiment/src/experiment/engine/obstacle_generator.py`)

**対象箇所**: L206-211

**現状**:
```python
segments = []
for i in range(len(centerline) - 1):
    p1 = centerline[i]
    p2 = centerline[i + 1]
    dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    segments.append((dist, p1, p2))
```

**改善案**:
```python
points = np.array(centerline)[:, :2]  # (N, 2)
diffs = np.diff(points, axis=0)
distances = np.linalg.norm(diffs, axis=1)
```

**期待効果**: センターラインポイント数が多い場合

**実装難易度**: 低

---

## 実装優先順位

### 🎯 基本方針: NumPy化 → JIT化

**重要**: NumPy配列化を先に実装してから、Numba JIT化を進める

**理由**:
1. Numba は NumPy配列を前提としている
2. 段階的な最適化により、各段階で効果測定とデバッグが容易
3. NumPy化だけでも一定の効果が得られる

---

### フェーズ1: NumPy配列化（低リスク・確実な効果）

| 順位 | 箇所 | ファイル | 優先度 | 実装難易度 | 期待効果 |
|------|------|----------|--------|------------|----------|
| 1 | Dashboard ダウンサンプリング | `dashboard/src/dashboard/generator.py` | ⭐⭐ | 低 | 低〜中 |
| 2 | ObstacleGenerator センターライン | `experiment/src/experiment/engine/obstacle_generator.py` | ⭐⭐ | 低 | 中 |
| 3 | ポリゴン生成 | `simulator/src/simulator/dynamics.py`<br>`simulator/src/simulator/obstacle.py` | ⭐ | 低 | 低 |

**目標**: 実装が簡単で副作用が少ない箇所から着手し、NumPy配列の扱いに慣れる

---

### フェーズ2: 重要箇所のNumPy配列化（中リスク・高効果）

| 順位 | 箇所 | ファイル | 優先度 | 実装難易度 | 期待効果 |
|------|------|----------|--------|------------|----------|
| 4 | obstacle.py ウェイポイント補間 | `simulator/src/simulator/obstacle.py` | ⭐⭐⭐ | 中 | 高 |
| 5 | Simulator 障害物状態リスト | `simulator/src/simulator/simulator.py` | ⭐⭐⭐ | 中 | 高 |
| 6 | ObstacleGenerator セグメント長 | `experiment/src/experiment/engine/obstacle_generator.py` | ⭐⭐ | 低 | 中 |

**目標**: 最も効果が期待できる箇所をNumPy配列化し、JIT化の準備を整える

---

### フェーズ3: Numba JIT化（NumPy化完了後）

| 順位 | 箇所 | ファイル | 優先度 | 実装難易度 | 期待効果 |
|------|------|----------|--------|------------|----------|
| 7 | obstacle.py ウェイポイント補間 | `simulator/src/simulator/obstacle.py` | ⭐⭐⭐ | 中 | 高 |
| 8 | dynamics.py 車両モデル | `simulator/src/simulator/dynamics.py` | ⭐⭐ | 低 | 低〜中 |

**目標**: NumPy配列化済みの箇所にJITコンパイルを適用し、さらなる高速化を図る

---

### ベンチマーク結果

各最適化の効果を記録します。測定条件は統一してください。

**測定条件**:
- シミュレーション: 20,000ステップ (200秒 @ 100Hz)
- 障害物数: 5個
- コマンド: `uv run experiment-runner agent=mpc`

| フェーズ | 箇所 |の実装前 (秒) | 実装後 (秒) | 改善率 | 実装日 | 備考 |
|---------|------|------------|------------|--------|--------|------|
| 1-1 | Dashboard ダウンサンプリング | - | - | - | 2025-12-26 | NumPy linspace化完了 |
| 1-2 | ObstacleGenerator センターライン | - | - | - | 2025-12-26 | NumPyベクトル化完了 |
| 1-3 | ポリゴン生成 | - | - | - | 2025-12-26 | NumPy化完了 |
| 2-1 | obstacle.py ウェイポイント補間 | 14.44 | 15.22 | -5.4% | 2025-12-26 | NumPyオーバーヘッドにより悪化 |
| 2-2 | Simulator 障害物状態リスト | (14.44) | (15.22) | - | - | 2-1により影響 |
| 2-3 | ObstacleGenerator セグメント長 | - | - | - | 2025-12-26 | NumPyベクトル化完了 |
| 3-1 | obstacle.py JIT化 | 15.22 | 15.15 | +0.4% | 2025-12-26 | JITにより微増だがベースラインには届かず |
| 3-2 | dynamics.py JIT化 | - | 15.15 | - | 2025-12-26 | 3-1と同時に計測 |

**最終結果**: **15.15秒** (ベースライン 14.44秒 比 **+4.9% 遅延**)

> [!CAUTION]
> **分析結果**: 毎ステップ `np.array` を生成するオーバーヘッドがJITの高速化効果を上回っています。
> 真の高速化には、`SimulatorObstacle` クラス内でNumPy配列をキャッシュする構造変更が必要です。

---

## 実装時の注意点

### ⚠️ 互換性

- **Pydanticモデルとの互換性**: NumPy配列はPydanticモデルに直接格納できない
  - 内部処理のみでNumPy配列を使用
  - 入出力はPydanticモデルを維持

### ⚠️ パフォーマンス測定

- **小規模データでのオーバーヘッド**: NumPy配列化やJITコンパイルのオーバーヘッドで逆に遅くなる可能性
  - 実装前後でベンチマークを実施
  - プロファイリングツール（`cProfile`, `line_profiler`）を活用

### ⚠️ 可読性

- NumPy配列化により可読性が下がる場合がある
  - 十分なコメントとドキュメントを追加
  - 型ヒントを明確に記述

### ⚠️ テスト

- 最適化後も既存のテストが通ることを確認
- 数値精度の変化に注意（浮動小数点演算の順序変更）

---

## ベンチマーク方法

### 推奨プロファイリング手順

1. **ベースライン測定**
   ```bash
   uv run experiment-runner experiment=profile
   ```

2. **詳細プロファイリング**
   ```python
   import cProfile
   import pstats

   profiler = cProfile.Profile()
   profiler.enable()
   # シミュレーション実行
   profiler.disable()

   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(20)
   ```

3. **最適化後の比較**
   - 実行時間
   - メモリ使用量
   - ステップあたりの処理時間

---

## 参考資料

- [Numba Documentation](https://numba.pydata.org/)
- [NumPy Performance Tips](https://numpy.org/doc/stable/user/performance.html)
- [Python Profiling Guide](https://docs.python.org/3/library/profile.html)

---

## 更新履歴

- **2025-12-26**: 初版作成
