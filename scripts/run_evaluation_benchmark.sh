#!/bin/bash
# 評価ベンチマーク実行スクリプト
# 障害物なし1ケース + 障害物あり5ケースを1セットで実行

set -e

# 引数チェック
if [ $# -ne 1 ]; then
    echo "Usage: $0 <model_checkpoint_dir>"
    echo "Example: $0 outputs/2025-12-29/20-07-58/checkpoints"
    exit 1
fi

MODEL_DIR="$1"
MODEL_PATH="${MODEL_DIR}/best_model.npy"

# モデルファイルの存在確認
if [ ! -f "$MODEL_PATH" ]; then
    echo "Error: Model file not found: $MODEL_PATH"
    exit 1
fi

echo "========================================="
echo "評価ベンチマーク実行"
echo "========================================="
echo "モデルパス: $MODEL_PATH"
echo ""
echo "実行シナリオ:"
echo "  - 障害物なし: 1ケース"
echo "  - 障害物あり: 5ケース (Seed 30000-30004)"
echo "========================================="
echo ""

# 評価実行
# 注: Hydra Multirunで複数パラメータを指定すると全組み合わせになるため、
#     障害物なしと障害物ありを別々に実行

echo "1/2: 障害物なし環境での評価..."
uv run experiment-runner -m \
  experiment=evaluation \
  ad_components=tiny_lidar \
  ad_components.model_path="$(pwd)/${MODEL_PATH}" \
  ad_components.nodes.tiny_lidar_net.params.model_path="$(pwd)/${MODEL_PATH}" \
  env=no_obstacle \
  env.obstacles.generation.seed=0

echo ""
echo "2/2: 障害物あり環境での評価..."
uv run experiment-runner -m \
  experiment=evaluation \
  ad_components=tiny_lidar \
  ad_components.model_path="$(pwd)/${MODEL_PATH}" \
  ad_components.nodes.tiny_lidar_net.params.model_path="$(pwd)/${MODEL_PATH}" \
  env=default \
  env.obstacles.generation.seed=30000,30001,30002,30003,30004

echo ""
echo "========================================="
echo "評価完了"
echo "========================================="
