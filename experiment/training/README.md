# Experiment Training

学習ロジック（データセット、トレーナー）を提供するパッケージです。

## 概要

このパッケージは、収集されたシミュレーションデータを使用してモデルを学習するための機能を提供します。
`experiment-runner` から呼び出されて使用されます。

## 機能

### 1. Dataset Management

MinIO (S3互換ストレージ) からデータを自動的にダウンロードし、PyTorch Datasetとして提供します。

- **`TrajectoryDataset`**: 模倣学習用のデータセット。シミュレーションログから状態と行動のペアを抽出します。
- **`FunctionDataset`**: 関数近似タスク用のデータセット。

### 2. Trainers

- **`Trainer`**: ニューラルネットワークコントローラーの学習を行います。
  - MLflowによる実験トラッキング（Loss, Metrics）
  - モデルの保存
  - 早期終了 (Early Stopping)
- **`FunctionTrainer`**: 単純な関数近似タスク用のトレーナー。

## Usage

通常は `experiment-runner` 経由で使用します。

```bash
# 学習の実行
uv run experiment-runner --config experiment/configs/experiments/imitation_learning_s3.yaml
```

### 設定例

```yaml
training:
  # データセット設定 (MinIO)
  dataset_project: "e2e_aichallenge"
  dataset_scenario: "pure_pursuit"
  dataset_version: "v1.0"
  dataset_stage: "raw"

  # 学習ハイパーパラメータ
  epochs: 100
  batch_size: 32
  learning_rate: 0.001
```

## ディレクトリ構成

```
experiment/training/
├── src/
│   └── experiment_training/
│       ├── data/           # Dataset実装
│       ├── trainer.py      # Imitation Learning Trainer
│       └── function_trainer.py # Function Approximation Trainer
├── scripts/                # ユーティリティスクリプト
│   ├── download_mlflow_data.py
│   └── generate_function_data.py
└── tests/                  # テスト
```
