# スタンドアロンPlanningコンポーネント詳細設計書

Autowareのプリセットを使用せず、CSV地図データをベースに静的障害物回避を行うPlanningコンポーネントのロジック詳細です。

## 1. 処理フロー概要

1.  **Map Loading**: センターラインCSV $(x, y, s, yaw)$ を読み込み、KDTree等を構築して高速な近傍探索を可能にする。
2.  **Localization**: 自車位置 $(x_{ego}, y_{ego})$ を取得し、センターライン上の現在地 $s_{ego}$ を特定。
3.  **Object Projection**: 検知した障害物群を Frenet 座標系 $(s_{obj}, l_{obj})$ に変換。
4.  **Avoidance Planning (Frenet)**:
    *   $s$ 空間上で障害物との衝突判定を行う。
    *   各障害物に対する個別のシフトプロファイル $l_i(s)$ を生成する。
    *   **Merge Logic**: 複数のプロファイルを合成し、最終的な目標オフセット関数 $l_{target}(s)$ を生成する。左右方向の競合も解決する。
5.  **Path Generation (Global)**:
    *   $l_{target}(s)$ を元のセンターライン座標に投影し、回避経路 $(x_{out}, y_{out})$ を生成する。

---

## 2. 詳細アルゴリズム

### 2.1. 座標変換 (Global $\leftrightarrow$ Frenet)

基本となるセンターラインを $P_{ref}(s) = (x_{ref}(s), y_{ref}(s))$ とします。任意の点 $P=(x, y)$ の Frenet 座標 $(s, l)$ は以下のように求めます。

1.  **$s$ の特定**:
    点 $P$ に最も近いセンターライン上の点 $P_{ref}(s_{nearest})$ を探索します。
    $$s = s_{nearest}$$

2.  **$l$ の計算**:
    センターラインの方位角を $\theta(s)$ とすると、法線ベクトルは $\vec{n}(s) = (-\sin\theta, \cos\theta)$ です。
    ベクトル $\vec{d} = P - P_{ref}(s)$ と $\vec{n}(s)$ の内積をとります。
    $$l = \vec{d} \cdot \vec{n}(s)$$
    *   $l > 0$: 進行方向左側
    *   $l < 0$: 進行方向右側

### 2.2. 障害物のフィルタリングとマッピング

各障害物 $O_i$ について、以下の条件を満たすものを回避対象とします。
1.  **前方判定**: $s_{obj} > s_{ego}$
2.  **距離判定**: $s_{obj} - s_{ego} < L_{lookahead}$
3.  **横位置判定**: $|l_{obj}| < W_{road} / 2$

### 2.3. 回避目標・シフト量の算出

#### A. 個別シフトプロファイルの生成
各障害物 $i$ について、単独で存在した場合のシフトプロファイル $l_i(s)$ を計算します。

1.  **目標シフト量 $\Delta l_i$**:
    $$\Delta l_i = \text{sign}(-l_{obj,i}) \cdot (W_{obj,i}/2 + W_{ego}/2 + M_{safe})$$
    (障害物の外側へ避ける方向)

2.  **区間決定 $[s_{start,i}, s_{end,i}]$**:
    必要な縦距離 $D_{avoid}$ を考慮して決定します。
    *   $s_{start,i} = s_{obj,i} - D_{front\_buffer} - D_{avoid}$
    *   $s_{end,i} = s_{obj,i} + L_{obj,i} + D_{rear\_buffer} + D_{avoid}$

3.  **補間関数**:
    区間外は 0、区間内は滑らかに $\Delta l_i$ に遷移する関数形を用います。

#### B. 複数障害物の合成 (Merging Logic)

**Case 1: 同じ方向への回避 (同符号)**
ある地点 $s$ において、左に避けるもの同士、または右に避けるもの同士の場合：
$$l_{target}(s) = \max(|l_i(s)|, |l_j(s)|) \cdot \text{sign}(l_i(s))$$
(絶対値が大きい方＝より大きく避ける方を採用)

**Case 2: 逆方向への回避 (異符号・スラローム)**
左に避けるプロフィール $l_L(s) > 0$ と、右に避けるプロフィール $l_R(s) < 0$ が同じ地点 $s$ で重なる場合：

1.  **通過可能性チェック**:
    その地点 $s$ における有効道幅 $W_{valid}(s)$ を確認します。
    $$W_{valid} = W_{road} - (\text{LeftObstacleEdge} - \text{RightObstacleEdge})$$
    もし $W_{valid} < W_{ego} + M_{margin}$ であれば、物理的に通過不能です。
    $\rightarrow$ **手前の障害物の前で停止 (Yield)** する計画に切り替えます。

2.  **通過可能なら合成**:
    左右それぞれの制約を満たす中間点を目標としますが、単純な和ではなく、遷移区間を考慮した合成が必要です。

    もっとも簡単な実装は、Frenet空間上で「左側の禁止領域」と「右側の禁止領域」を定義し、その**中央**を通るパスを生成することです。
    $$l_{target}(s) = \frac{L_{bound\_min}(s) + L_{bound\_max}(s)}{2}$$
    ここで
    $L_{bound\_min}(s) = \max(\text{RightObstacleEdges})$
    $L_{bound\_max}(s) = \min(\text{LeftObstacleEdges})$

    これにより、左障害物と右障害物の間を縫うような（スラローム状の）パスが生成されます。

### 2.4. 最終パス合成 (Frenet to Global)

合成された $l_{target}(s)$ を用いて、グローバル座標系での目標パスを生成します。

$$P_{out}(s) = P_{ref}(s) + l_{target}(s) \cdot \vec{n}(s)$$

---

## 3. クラス設計案

### `AvoidancePlanner`
*   `plan(ego_pose, obstacles, ref_path)`:
    1.  `ObstacleManager` から障害物リストを取得
    2.  各障害物について `ShiftProfile` ($l_i(s)$) を生成
    3.  **`merge_shift_profiles()`**:
        *   まず左右それぞれの「進入禁止ライン（Drivable Bound）」を作成する。
        *   $s$ ごとに左右のBoundの幅が自車幅以上かチェック（**Collision Check**）。
        *   NGなら手前で停止。OKなら左右Boundの中点または推奨ラインを $l_{target}(s)$ とする。
    4.  $l_{target}(s)$ を `FrenetConverter` でグローバル座標へ再変換
    5.  Trajectory メッセージを出力

## 4. 拡張性
*   **速度計画の統合**: カーブ曲率 $RefCurvature$ に基づく減速ロジックの追加。
