# 【完結編】教師を超えろ！障害物回避への挑戦

## 0. TL;DR
- **What**: 「Track Forward」という障害物回避特化のデータ収集環境を構築し、Tiny Lidar Netを学習させた。
- **Result**: 障害物なし環境では**100%完走**、障害物あり環境では約**33%の成功率**を達成（改善中）。
- **So What**: 単純な教師あり学習でも、**データ収集環境自体の工夫**（カリキュラム）によって、障害物回避の基礎能力を獲得できることを実証した。

---

## 1. 目的（問題意識・課題感）
- **What**: 確実に障害物を回避し、周回し続けられるAIモデルを作りたい。
- **Why**:
  - Vol.2で障害物なしコースは100%完走できたが、障害物がある環境では失敗する。
  - 単純なPure Pursuit (教師役) では、障害物を避ける際のカクつきやオーバーシュートが課題。
  - まばらにしか障害物が出ない環境で学習しても、回避行動のデータが少なすぎて学習効率が悪い。
- **Goal**: 「Track Forward」戦略を用いて高品質な回避データを大量収集し、教師アルゴリズムを超える滑らかな回避を実現する。

## 2. 実験設定（解決策・作ったもの）
### 2.1 Approach Selection (アプローチの選定理由)
- **Alternatives**:
  - ひたすらコースを周回させて、偶発的に障害物に出会うのを待つ。
  - ルールベースで回避するロジック（Force Field法など）を書いて終わりにする。
- **Reason**:
  - 偶発的な遭遇では学習効率が悪すぎる（1周で1〜2回しか障害物に出会わない）。
  - ルールベースでは柔軟性がなく、複雑なシナリオに対応できない。
  - **Track Forward**: 常に障害物がある状況を作り出し、短時間で大量の回避データを収集するアプローチを採用。

### 2.2 Proposed Method: Track Forward Strategy
回避行動を濃縮して学習させるためのデータ収集環境。

- **常に障害物を配置**: エピソード開始時、必ず車両の10m前方に障害物を設置。
  - 10mという距離は速度3m/sで約3秒。回避に十分な時間を確保しつつ、反応が遅れた場合は衝突する緊張感のある距離。
  - 障害物の大きさは車両と同程度（幅1.3m、長さ2.0m）で固定。
  - 障害物の位置はレーン中央に固定せず、左右にオフセットあり（-1.5m〜+1.5m）。
- **短時間エピソード**: 7秒でエピソード終了（回避完了直後）。
- **効果**: 直線を走るだけの「暇な時間」を排除し、回避密度を極限まで高める。

### 2.3 Experiment Setup
- **Dataset Ratio**: Track Forward (80%) + Random Start (20%)。
  - 100% Track Forwardでは基礎走行能力が落ちるため、Random Startも混合。
- **Teacher Algorithm**: Lateral Shift (回避点生成) + Pure Pursuit。
  - Lateral Shiftは障害物の横方向座標に基づいて固定オフセットで回避経路を生成。
- **Model**: Tiny Lidar Net (1D CNN)。
- **Dataset**:
    - TF Train: 200, TF Val: 50
    - RS Train: 50, RS Val: 10

### 2.4 Metrics (評価指標)
- **Avoidance Success Rate**: 障害物に衝突せず、かつコースアウトせずに回避できた割合。
  - 衝突判定：バウンディングボックス同士の干渉。
- **Goal Reached Rate**: ゴールまで到達した割合。

## 3. 前提環境 (Prerequisites)
- **Simulator**: Vol.1で作成したPython Simulator (障害物対応済)。
- **Config**: `experiment/conf/experiment/data_collection_track_forward.yaml`

## 4. 具体的な検証手順 (Concrete Steps)

再現性を担保するため、`uv run` を用いた実行コマンドを記載します。

### Step 1: 依存関係のセットアップ (初回のみ)
```bash
uv sync
```

### Step 2: 障害物回避の学習パイプライン実行
既存の `run_mlops_pipeline_obstacle.py` を使用します。

```bash
# args: --version=データセットバージョン, --tf-train/val=Track Forward数, --rs-train/val=Random Start数
uv run experiment/scripts/run_mlops_pipeline_obstacle.py \
    --version v3_blog \
    --tf-train 200 --tf-val 50 \
    --rs-train 50 --rs-val 10 \
    --epochs 5
```

### Step 3: 評価結果の確認 (大規模実験からの参照)

以下は、より大規模なデータ（TF 1000ep + RS 500ep）で学習した過去の実験結果です。

**評価環境**: default (障害物あり)
- **total_episodes**: 6
- **success_rate**: 33.3% (2/6 goal_reached)
- **failure_breakdown**: off_track 4エピソード

**評価環境**: no_obstacle
- **success_rate**: 100% (1/1 goal_reached)

## 5. 結果（結果概要）
- **障害物なし**: 100%完走（Vol.2の成果が維持されている）。
- **障害物あり**: 33%成功率（6エピソード中2エピソードでゴール到達、4エピソードでコースアウト）。
- **考察**: 回避動作自体は学習できているが、回避後の復帰動作でコースアウトするケースが多い。

## 6. ログ詳細
- 評価結果ディレクトリ: `outputs/mlops/v8_184249_full_20260106_115135/evaluation/standard/`
- Foxglove再生: `evaluation_summary.json` 内の各エピソードの `foxglove` リンクからMCAPを再生可能。

## 7. 考察

### 7.1 成功の要因
- **Track Forward戦略の有効性**: 回避行動のデータ密度を高めることで、少ないエピソード数でも回避の基礎動作を学習できた。
- **教師アルゴリズムの限界**: Lateral Shift + Pure Pursuitは回避は得意だが、回避後のレーン復帰が急すぎる傾向があり、学習モデルにもその癖が引き継がれている。

### 7.2 今後の課題
- **Jerk最小化**: 滑らかな経路生成（Jerk = 加加速度の最小化）を教師アルゴリズムに組み込むことで、より人間らしい回避挙動を学習させる。
- **データ量のスケーリング**: 現在の数百エピソードから数万エピソードへスケールアップすることで、成功率の向上が期待できる（Scaling Law検証）。
- **強化学習への移行**: 教師あり学習の限界が見えてきたら、BCで学習したモデルをベースに強化学習でファインチューニングすることも検討。

### 7.3 シミュレータ内製化の勝利
- **結論**: データ収集環境自体を自由にハックできる（Track Forwardを作るなど）ことが、E2E自動運転開発における最強の武器。
- 自作Pythonシミュレータ + MLOps環境により、アイデアを即座に実験・検証できるサイクルが完成した。

## 8. 参考文献 (References)
- [Behavioral Cloning for Autonomous Driving](https://arxiv.org/abs/1604.07316)
- [Curriculum Learning](https://proceedings.mlr.press/v9/bengio09a.html): Track Forwardは一種のカリキュラム学習とみなせる。
