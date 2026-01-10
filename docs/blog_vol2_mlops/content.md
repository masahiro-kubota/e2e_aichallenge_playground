# 【MLOps】自作シミュレータで回す高速開発サイクル

## 0. TL;DR
- **What**: 並列データ収集・学習・評価を自動化するMLOpsパイプラインを構築し、「Random Start」戦略を導入した。
- **Result**: 障害物なしコースにおいて、単純なモデルで **完走率100%** を達成した。
- **So What**: 手動オペレーションを排除したことで、モデル改善のPDCAサイクルを高速に回せるようになった。

---

## 1. 目的（問題意識・課題感）
- **What**: MLOpsパイプラインを構築し、Tiny Lidar Netモデルで障害物なしコースを100%完走させたい。
- **Why**:
  - シミュレータがあっても、データ収集→学習→評価のフローが手動では効率が悪い。
  - そもそも「まともに走れる」モデルを作るためのデータ収集戦略（カリキュラム）が必要。
- **Goal**: 自動化されたパイプラインを確立し、Random Start戦略を用いて堅牢なベースモデルを作成する。

## 2. 実験設定（解決策・作ったもの）
### Approach Selection (アプローチの選定理由)
<!-- QUESTION: なぜ手動データ収集ではなくMLOpsパイプラインなのか、なぜ他手法ではなくRandom Startなのか？ -->
- **Alternatives**:
  - 手動操作（キーボード）でデータを集める。
  - 強化学習 (RL) をいきなり適用する。
- **Reason**:
  - <!-- ANSWER: 手動は再現性と量が不足、RLは報酬設計が難しいなど、Random Startの優位性を書いてください -->

### Proposed Method: MLOps Pipeline & Random Start
#### 1. MLOps Pipeline
- **Collection**: `joblib`による並列データ収集（CPUコアフル稼働）。
- **Extraction**: 成功エピソードのみを抽出・加工。失敗データは学習に使わない（Noisy Data Filtering）。
- **Training**: PyTorch Lightning + WandB/MLflow管理。
- **Evaluation & Visualization**: 結果をJSONに集約し、Foxglove (MCAP) で可視化。

#### 2. Random Start Strategy
- コース上のランダムな位置・姿勢・速度からスタートさせるデータ収集手法。
- 理想的な走行ラインだけでなく、「少し逸脱した状態からの復帰」を網羅的に学習させる（擬似的なDAgger効果）。

### Experiment Setup
- **環境**: Track Forward (Obstacleなし版)。
- **モデル**: Tiny Lidar Net (1D CNN)。 <!-- QUESTION: なぜ2D CNNやPointNetではなく1D CNNなのか？軽量化のため？ -->
- **教師**: Pure Pursuit。 <!-- QUESTION: 完璧ではない教師（Pure Pursuit）を選んだ理由は？（実装が楽だから？これでも十分だから？） -->
- **Dataset**:
    - Train Episodes: 8000
    - Val Episodes: 2000

### Metrics (評価指標)
- **完走率 (Success Rate)**: 全エピソード中、ゴールライン（または一定距離）を通過した割合。
- **Course Deviation**: センターラインからの平均逸脱距離。

## 3. 前提環境 (Prerequisites)
- **OS/Hardware**: Vol.1と同様。
- **Experiment Tracking**: WandB or MLflow account.
- **Visualization**: Foxglove Studio (Desktop or Web).

## 4. 実行コマンド
再現性を担保するため、`uv run` を用いた実行コマンドを記載します。

```bash
# 依存関係のインストール（初回のみ）
uv sync

# パイプライン実行（データ収集〜学習〜評価）
# args: obs_type=no_obstacle, strategy=random_start
uv run experiment/scripts/run_mlops_pipeline.py \
    --obs_type no_obstacle \
    --strategy random_start
```

## 5. 結果（結果概要）
- **完走率**: 100%達成（障害物なし）。
- **Sim-to-Sim転移**: 自作シミュレータで学習したモデルを、本家AWSIM (Unity) 環境に戻しても完走することを確認。
- **学習曲線**: 成功データのみを使用することで、Lossが安定して低下。
    - ![Loss Curve](path/to/loss_curve.png)

## 6. ログ詳細
- WandB実験ログ: [Link to WandB]
- 評価結果 (Foxglove): `evaluation/results/v1_random_start/summary.json`

## 7. 考察
- Random Start戦略により、モデルが「復帰能力」を獲得したことが完走率100%の勝因。
- 失敗データを学習に含めると、モデルが迷う挙動を見せたため、成功データのみのBehavioral Cloning (BC) が今回は有効だった。
- これでベースラインは完成。次は障害物回避へ（Vol.3へ続く）。

## 8. 参考文献 (References)
- [WandB Documentation](https://docs.wandb.ai/)
- [Foxglove Docs](https://foxglove.dev/docs)
