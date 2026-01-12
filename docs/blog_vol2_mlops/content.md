# 【MLOps】自作シミュレータで回す高速開発サイクル

## 0. TL;DR
- **What**: 並列データ収集・学習・評価を自動化するMLOpsパイプラインを構築し、「Random Start」戦略を導入した。
- **Result**: 障害物なしコースにおいて、わずか200エピソードのデータで **完走率100%** を達成した（5/5エピソード成功）。
- **So What**: 手動オペレーションを排除したことで、モデル改善のPDCAサイクルを高速に回せるようになった。

---

## 1. 目的（問題意識・課題感）
- **What**: MLOpsパイプラインを構築し、Tiny Lidar Netモデルで障害物なしコースを100%完走させたい。
- **Why**:
  - シミュレータがあっても、データ収集→学習→評価のフローが手動では効率が悪い。
  - そもそも「まともに走れる」モデルを作るためのデータ収集戦略（カリキュラム）が必要。
- **Goal**: 自動化されたパイプラインを確立し、Random Start戦略を用いて堅牢なベースモデルを作成する。

## 2. 実験設定（解決策・作ったもの）
### 2.1 Approach Selection (アプローチの選定理由)
- **Alternatives**:
  - 手動操作（キーボード）でデータを集める。
  - 強化学習 (RL) をいきなり適用する。
- **Reason**:
  - 手動は再現性と量が不足し、数万エピソード規模のデータ収集が現実的に不可能。
  - 強化学習は報酬設計が難しく、初期探索の効率も悪い。シミュレータの高速性を活かし、まずは教師あり学習（BC）でベースラインを確立するのが効率的。

### 2.2 Proposed Method: MLOps Pipeline & Random Start
#### MLOps Pipeline
- **Collection**: `hydra-joblib-launcher`による並列データ収集（CPUコアフル稼働）。
  - `joblib`を選んだ理由は、Hydra設定ファイルとの親和性が高く、追加の設定なしで並列分散が可能なため。`Ray`はオーバースペック、`multiprocessing`は設定の手間が大きい。
- **Extraction**: 成功エピソードのみを抽出・加工。失敗データは学習に使わない（Noisy Data Filtering）。
  - 成功の定義：コースアウト（`off_track`）や衝突（`collision`）せずにゴール（`goal_reached`）に到達すること。
- **Training**: PyTorch + MLflow/WandB管理。
  - Optimizer: AdamW, Learning Rate: 3e-4, Batch Size: 64。
- **Evaluation & Visualization**: 結果をJSONに集約し、Foxglove (MCAP) で可視化。

#### Random Start Strategy
- コース上のランダムな位置・姿勢・速度からスタートさせるデータ収集手法。
  - ランダムの分布はコース幅いっぱいに均一分布。初期速度は0〜3m/sの範囲でランダム化。
- 理想的な走行ラインだけでなく、「少し逸脱した状態からの復帰」を網羅的に学習させる（擬似的なDAgger効果）。

### 2.3 Experiment Setup
- **環境**: Track Forward (Obstacleなし版)、`env=no_obstacle`設定。
- **モデル**: Tiny Lidar Net (1D CNN)。
  - 入力: LiDARのRange値（1080次元ベクトル）。出力: ステアリング角のみ（速度は固定）。
  - 軽量化のため1D CNNを採用。PointNetは点群座標が必要なため入力形式が異なる。
- **教師**: Pure Pursuit。
  - 完璧ではないが、実装が簡単で安定した教師データを生成できる。Lookahead Distance = 4.0m。
- **Dataset**:
    - Train Episodes: 200
    - Val Episodes: 50

### 2.4 Metrics (評価指標)
- **完走率 (Success Rate)**: 全エピソード中、ゴールを通過した割合。
- **Course Deviation**: センターラインからの平均逸脱距離（Lanelet2マップとの照合で計算）。

## 3. 前提環境 (Prerequisites)
- **OS/Hardware**: Vol.1と同様 (Ubuntu 24.04, Intel Core i9-13900K)。
- **Experiment Tracking**: MLflow (ローカル) or WandB。
- **Visualization**: Foxglove Studio (Desktop or Web)。

## 4. 具体的な検証手順 (Concrete Steps)

再現性を担保するため、`uv run` を用いた実行コマンドを記載します。

### Step 1: 依存関係のセットアップ (初回のみ)
```bash
uv sync
```

### Step 2: パイプライン実行（データ収集〜学習〜評価）
Vol.2用に作成した `run_mlops_pipeline_v2.py` を使用します。

```bash
# args: --version=データセットバージョン, --rs-train=Train用RS数, --rs-val=Val用RS数, --epochs=学習エポック数
uv run experiment/scripts/run_mlops_pipeline_v2.py \
    --version v2_blog \
    --rs-train 200 --rs-val 50 \
    --epochs 5 > docs/blog_vol2_mlops/pipeline_log.txt
```

**実行結果 (Log)**: [pipeline_log.txt](./pipeline_log.txt)

### Step 3: 評価結果の確認

**評価結果 (Output)**: [evaluation_summary.json](./evaluation_summary.json)

![Evaluation Summary](images/evaluation_summary.png)
*（評価結果のサマリー。5エピソード全てでゴールに到達し、完走率100%を達成。）*

## 5. 結果（結果概要）
- **完走率**: **100%達成**（5エピソード中5エピソード成功、`goal_reached`）。
- **学習曲線**: Train Loss: 0.004666, Val Loss: 0.007240 (Best)。成功データのみを使用することで、Lossが安定して低下。
- **Sim-to-Sim転移**: 自作シミュレータで学習したモデルを、本家AWSIM (Unity) 環境に戻しても完走することを確認。

## 6. ログ詳細
- MLflow実験ログ: [http://localhost:5000/#/experiments/158](http://localhost:5000/#/experiments/158)
- 評価結果 (Foxglove): 各エピソードの `evaluation_summary.json` 内の `foxglove` リンクから再生可能。

## 7. 考察
- Random Start戦略により、モデルが「復帰能力」を獲得したことが完走率100%の勝因。
- わずか200エピソード（約3分間のデータ収集+15秒の学習）でも、シンプルなコースであれば十分な性能が得られることがわかった。
- 失敗データを学習に含めると、モデルが迷う挙動を見せたため、成功データのみのBehavioral Cloning (BC) が今回は有効だった。
- これでベースラインは完成。次は障害物回避へ（Vol.3へ続く）。

## 8. 参考文献 (References)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [Foxglove Docs](https://foxglove.dev/docs)
