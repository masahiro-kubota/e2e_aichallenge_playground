# Collision Avoidance Options

MPC軌道計画における衝突回避手法の詳細な比較と実装ガイド。

## Option 1: Circle Approximation (円形包絡線近似)

### 概要

長方形の車両と障害物をそれぞれ包含する円で近似し、円同士の距離で衝突判定を行う。

### 数式

```
# 車両の包絡円半径
r_vehicle = sqrt((vehicle_length/2)^2 + (vehicle_width/2)^2)

# 障害物の包絡円半径
r_obstacle = sqrt((obstacle_length/2)^2 + (obstacle_width/2)^2)

# 中心間距離
d_center = sqrt((x_vehicle - x_obstacle)^2 + (y_vehicle - y_obstacle)^2)

# 制約
d_center >= r_vehicle + r_obstacle + safety_margin
```

### メリット

- ✅ 実装が最もシンプル
- ✅ 計算コストが最小(1制約/障害物)
- ✅ 常に保守的(安全側)
- ✅ 微分可能で最適化に適している

### デメリット

- ❌ 過度に保守的(通れる隙間を通れないと判断)
- ❌ 車両の向きを考慮しない
- ❌ 狭い通路では使えない

### 適用シーン

- 障害物が疎に配置されている
- 最速で結果が欲しい
- プロトタイプ検証

### 実装例

```python
def circle_approximation_distance(
    vehicle_x, vehicle_y,
    obstacle_x, obstacle_y,
    obstacle_width, obstacle_length
):
    vehicle_radius = ca.sqrt(
        (vehicle_length / 2.0)**2 + (vehicle_width / 2.0)**2
    )
    obstacle_radius = ca.sqrt(
        (obstacle_length / 2.0)**2 + (obstacle_width / 2.0)**2
    )
    center_distance = ca.sqrt(
        (vehicle_x - obstacle_x)**2 + (vehicle_y - obstacle_y)**2
    )
    return center_distance - vehicle_radius - obstacle_radius
```

---

## Option 2: Four Corners Distance (車両4隅距離) ← **現在の実装**

### 概要

車両の4隅の各点が、全ての障害物から一定距離以上離れていることを保証する。

### 数式

```
# 車両の4隅を計算
corners = compute_vehicle_corners(x, y, θ, width, length)

# 各隅が各障害物から離れている
for corner in corners:
    for obstacle in obstacles:
        distance(corner, obstacle) >= safety_margin
```

### 点と長方形の距離計算

```python
# 点を障害物のローカル座標系に変換
local_x = (px - obs_x) * cos(obs_θ) + (py - obs_y) * sin(obs_θ)
local_y = -(px - obs_x) * sin(obs_θ) + (py - obs_y) * cos(obs_θ)

# 各辺までの距離
dx_edge = |local_x| - length/2
dy_edge = |local_y| - width/2

# 距離
if dx_edge <= 0 and dy_edge <= 0:
    # 点が内部
    distance = max(dx_edge, dy_edge)
else:
    # 点が外部
    distance = sqrt(max(dx_edge, 0)^2 + max(dy_edge, 0)^2)
```

### メリット

- ✅ 精度と速度のバランスが良い
- ✅ 車両の向きを考慮
- ✅ 狭い隙間も通れる
- ✅ 微分可能(CasADiで自動微分)
- ✅ デバッグしやすい(各隅の位置を可視化可能)

### デメリット

- ⚠️ 制約数が増える(4点 × 障害物数)
- ⚠️ Option 1より計算時間が長い

### 適用シーン

- **推奨**: 実用性と精度のバランス
- 狭い隙間も通りたいが、計算時間も抑えたい
- ほとんどのユースケース

### 計算コスト

- 制約数: 4 × 障害物数
- 例: 10障害物 → 40制約
- 予想求解時間: 0.3-1.0秒 (30mホライズン)

---

## Option 3: Separating Axis Theorem (SAT) ← **将来実装**

### 概要

Separating Axis Theorem (分離軸定理)を用いて、2つの長方形間の正確な最小距離を計算する。

### 理論

2つの凸多角形が分離しているとき、少なくとも1つの分離軸が存在する。長方形の場合、以下の4つの軸をチェックすれば十分:

1. 車両の長軸方向
2. 車両の短軸方向
3. 障害物の長軸方向
4. 障害物の短軸方向

### 数式(概要)

```
# 各分離軸での投影を計算
for axis in [vehicle_axes, obstacle_axes]:
    # 車両の投影
    vehicle_projection = project_rectangle(vehicle, axis)
    
    # 障害物の投影
    obstacle_projection = project_rectangle(obstacle, axis)
    
    # 分離距離
    separation = min(
        obstacle_projection.min - vehicle_projection.max,
        vehicle_projection.min - obstacle_projection.max
    )
    
    # 最小分離距離を記録
    min_separation = min(min_separation, separation)

# 制約
min_separation >= safety_margin
```

### メリット

- ✅ 最も正確(理論上通れる場所は全て通れる)
- ✅ 長方形の形状を完全に考慮
- ✅ 密集した障害物配置でも有効

### デメリット

- ❌ 実装が複雑
- ❌ 計算コストが高い
- ❌ 微分可能性の保証が難しい(要工夫)

### 適用シーン

- 最高精度が必要
- 計算時間は許容できる(オフライン計画)
- 密集した障害物配置

### 実装ガイドライン(将来用)

1. **投影関数の実装**: 長方形を軸に投影
2. **CasADi互換性**: `ca.if_else`や`ca.fmin`/`ca.fmax`を使用
3. **数値安定性**: 小さな角度での除算に注意
4. **初期値の工夫**: Option 2の結果を初期値として使用

### 参考実装(疑似コード)

```python
def sat_distance(vehicle, obstacle):
    axes = [
        vehicle.x_axis, vehicle.y_axis,
        obstacle.x_axis, obstacle.y_axis
    ]
    
    min_separation = float('inf')
    
    for axis in axes:
        v_proj = project_rectangle(vehicle, axis)
        o_proj = project_rectangle(obstacle, axis)
        
        sep = ca.fmin(
            o_proj[0] - v_proj[1],  # obstacle.min - vehicle.max
            v_proj[0] - o_proj[1]   # vehicle.min - obstacle.max
        )
        
        min_separation = ca.fmin(min_separation, sep)
    
    return min_separation
```

---

## 比較表

| 項目 | Option 1 (Circle) | Option 2 (Four Corners) | Option 3 (SAT) |
|-----|------------------|------------------------|----------------|
| 精度 | ⭐⭐☆☆☆ | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐⭐ |
| 計算時間 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐☆☆ | ⭐⭐☆☆☆ |
| 実装難易度 | 簡単 | 中程度 | 難しい |
| 制約数(10障害物) | 10 | 40 | 10 |
| 狭い隙間 | ❌ | ✅ | ✅ |
| 実装状況 | ✅ | ✅ (デフォルト) | 📋 将来 |

## 推奨事項

1. **まずOption 2で開始**: 実用性と精度のバランスが最適
2. **計算時間が問題なら**: Option 1にフォールバック
3. **精度が不足なら**: Option 3の実装を検討

## 切り替え方法

設定ファイル(`experiment/conf/agent/mpc.yaml`)で変更:

```yaml
planning:
  collision_method: "four_corners"  # または "circle"
```

Option 3は将来実装予定のため、現在は選択できません。
