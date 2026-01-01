# Self-Driving Simulator MLOps Pipeline Guide

このドキュメントでは、**Spatial-Temporal LidarNet** および **TinyLidarNet** の開発で使用された、データ収集から学習、評価までの完全なワークフローを解説します。

---

## 0. アーキテクチャ概要

| モデル | 特徴 | 用途 |
|---|---|---|
| **TinyLidarNet** | 単一フレーム入力 (Batch, 1, 1080) | 軽量、ベースライン |
| **Spatial-Temporal LidarNet** | 時系列入力 (Batch, 1, 20, 1080) | **推奨**: 高速域(10m/s)での安定性、遅延耐性 |

---

## 1. データ収集 (Data Collection)

シミュレーターを実行し、ランダムな初期位置からゴールを目指すエピソードを大量に収集します。

**コマンド (1000エピソード収集の例):**
# 障害物なし、ランダムスタート設定で実行
# 事前に experiment/conf/experiment/data_collection_random_start.yaml の seed range を変更
uv run experiment-runner -m \
    experiment=data_collection_random_start \
    experiment.name=collect_no_obstacle_v7_3000
```

- **出力先**: `outputs/<date>/<time>/<experiment_name>/episode_XXXX/simulation.mcap`
- **所要時間**: 並列数によりますが、数時間程度。

---

## 2. データ選別 & 分割 (Filtering & Splitting)

収集したデータの中から**「壁に衝突していない」**（ゴール到達または一定時間トラック内を走行してタイムアウト）エピソードのみを抽出し、**8:2** の割合で Train/Val に分割します。

**スクリプト:** `scripts/split_successful_data.py`

```bash
# 使用法: python split_successful_data.py <入力ルート> <出力ベース> <Train割合> <サフィックス>
uv run scripts/split_successful_data.py \
    outputs/2026-01-01/11-34-57 \
    data/raw \
    0.8 \
    v7_3000
```

- **結果**:
    - `data/raw/train_v7_3000/`: 学習用MCAPへのシンボリックリンク
    - `data/raw/val_v7_3000/`: 検証用MCAPへのシンボリックリンク

---

## 3. 特徴量抽出 (Feature Extraction)

MCAPファイルからLiDARデータと操作量（ステアリング、アクセル）を抽出し、学習用の `.npy` 形式に変換・正規化します。

**スクリプト:** `scripts/prepare_fine_tuning_data_v3.py` (または同等の処理)

```bash
# Trainデータの処理
uv run scripts/prepare_fine_tuning_data_v3.py --input-dir data/raw/train_v7_3000 --output-dir data/processed/train_v7_3000

# Valデータの処理
uv run scripts/prepare_fine_tuning_data_v3.py --input-dir data/raw/val_v7_3000 --output-dir data/processed/val_v7_3000
```
※スクリプト内のパスは適宜調整が必要な場合があります。

- **出力**: `scans.npy` (入力), `steers.npy`, `accelerations.npy` (正解ラベル)

---

## 4. モデル学習 (Training)

作成したデータセットを使ってモデルを学習させます。

### A. Spatial-Temporal LidarNet (推奨)
時系列モデルの学習です。

```bash
uv run ad_components/control/spatial_temporal_lidar_net/scripts/train.py \
    --train-dir data/processed/train_v7_3000 \
    --val-dir data/processed/val_v7_3000 \
    --checkpoint-dir checkpoints/spatial_temporal_lidar_net_v7_3000 \
    --epochs 50 \
    --batch-size 32 \
    --num-frames 20  # 過去20フレームを使用
```

### B. TinyLidarNet
単一フレームモデルの学習です。

```bash
uv run ad_components/control/tiny_lidar_net/scripts/train.py \
    --train-dir data/processed/train_v7_3000 \
    --val-dir data/processed/val_v7_3000 \
    --checkpoint-dir checkpoints/tiny_lidar_net_v7_3000 \
    --model large \
    --epochs 50
```

**重要**: 学習後、TinyLidarNetはPyTorch形式(`.pth`)からNumPy形式(`.npy`)への変換が必要です。
```bash
uv run ad_components/control/tiny_lidar_net/scripts/convert_weight.py \
    --ckpt checkpoints/tiny_lidar_net_v7_3000/best_model.pth \
    --output checkpoints/tiny_lidar_net_v7_3000/best_model.npy
```

---

## 5. 評価 (Evaluation)

学習済みモデルをシミュレーター上で評価します。

### A. Spatial-Temporal LidarNet
```bash
# 障害物なし、センターラインスタート(seed=0)での60秒走行テスト
# ターゲット速度を変更する場合の例 (10.0 -> 5.0)
uv run experiment-runner experiment=evaluation \
    ad_components=spatial_temporal_lidar \
    ad_components.model_path=$(pwd)/checkpoints/spatial_temporal_lidar_net_v7_3000/best_model.pth \
    env=no_obstacle \
    ad_components.nodes.spatial_temporal_lidar_net.params.target_velocity=10.0
```

### B. TinyLidarNet
```bash
# モデルパスとターゲット速度を指定可能
uv run experiment-runner experiment=evaluation \
    ad_components=tiny_lidar \
    ad_components.model_path=$(pwd)/checkpoints/tiny_lidar_net_v7_3000/best_model.npy \
    env=no_obstacle \
    ad_components.nodes.tiny_lidar_net.params.target_velocity=10.0
```

---

## 6. 結果の分析

評価実行後、出力された `simulation.mcap` を **Foxglove** で確認します。
ターミナルに表示されるリンクをクリックするか、ブラウザで `https://app.foxglove.dev` を開き、ローカルのMCAPファイルをロードしてください。

**確認ポイント**:
- **Trajectory**: 車両がコースを逸脱していないか
- **Steering**: ステアリング操作が滑らかか、発散していないか
- **Checkpoints**: 緑色のチェックポイントを通過できているか
