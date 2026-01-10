# 【完結編】教師を超えろ！障害物回避への挑戦

## 0. TL;DR
- **What**: 「Track Forward」という障害物回避特化のデータ収集環境を構築し、Tiny Lidar Netを学習させた。
- **Result**: 教師アルゴリズム (Pure Pursuit) よりも**滑らか**で**回避成功率が高い**モデルを獲得した。
- **So What**: 単純な教師あり学習でも、**データ収集環境自体の工夫**（カリキュラム）によって、教師を超える性能が出せることを実証した。

---

## 1. 目的（問題意識・課題感）
- **What**: 確実に障害物を回避し、周回し続けられるAIモデルを作りたい。
- **Why**:
  - 単純なPure Pursuit (教師役) では、障害物を避ける際のカクつきやオーバーシュートが課題。
  - まばらにしか障害物が出ない環境で学習しても、回避行動のデータが少なすぎて学習効率が悪い。
- **Goal**: 「Track Forward」戦略を用いて高品質な回避データを大量収集し、教師アルゴリズムを超える滑らかな回避を実現する。

## 2. 実験設定（解決策・作ったもの）
### Approach Selection (アプローチの選定理由)
<!-- QUESTION: なぜ普通に周回させるのではなく、Track Forwardという特殊な環境を作ったのですか？ -->
- **Alternatives**:
  - ひたすらコースを周回させて、偶発的に障害物に出会うのを待つ。
  - ルールベースで回避するロジック（Force Field法など）を書いて終わりにする。
- **Reason**:
  - <!-- ANSWER: 偶発的な遭遇では学習効率が悪すぎる、ルールベースでは柔軟性がない、などの理由を記載 -->

### Proposed Method: Track Forward Strategy
回避行動を濃縮して学習させるためのデータ収集環境。
- **常に障害物を配置**: エピソード開始時、必ず車両の10m前方に障害物を設置。
  <!-- QUESTION: 10mという距離はどう決めた？速度3m/sだと3秒弱。これより短いと回避不能？ -->
  <!-- QUESTION: 障害物の大きさは？固定？ランダム？ -->
  <!-- QUESTION: 障害物の位置はレーン中央固定？オフセットあり？ -->
- **短時間エピソード**: 7秒でエピソード終了（回避完了直後）。
  <!-- QUESTION: 7秒で十分？回避後に元のレーンに戻る動作まで含んでいる？ -->
- **効果**: 直線を走るだけの「暇な時間」を排除し、回避密度を極限まで高める。
  <!-- QUESTION: これによってデータ効率は何倍くらいになった感覚値はありますか？ -->

### Experiment Setup
- **Dataset Ratio**: Random Start (10%) + Track Forward (90%)。 <!-- QUESTION: なぜこの9:1という比率にしたのですか？ -->
  <!-- QUESTION: 100% Track Forwardではダメだった？基礎走行能力が落ちる？ -->
  - 基礎走行能力と回避能力のバランスを取るための混合比率。
- **Teacher Algorithm**: Lateral Shift (回避点生成) + Pure Pursuit。 <!-- QUESTION: Lateral Shiftはどうやって生成していますか？（固定オフセット？サイン波？） -->
  <!-- QUESTION: 経路生成時に滑らかさ（Jerk最小化）は考慮していますか？ -->
- **Model**: Tiny Lidar Net (1D CNN)。

### Metrics (評価指標)
- **Avoidance Success Rate**: 障害物に衝突せず、かつコースアウトせずに回避できた割合。
  <!-- QUESTION: 衝突判定の閾値は？バウンディングボックス同士の干渉？ -->
- **Lateral Jerk (横加加速度)**: 挙動の滑らかさの指標。値が小さいほど、人間にとって快適で安定した運転とされる。
  <!-- QUESTION: Jerkの計算式は？加速度の微分？ノイズ処理はしましたか？ -->
  <!-- QUESTION: サンプリング周波数は？ -->

## 3. 前提環境 (Prerequisites)
- **Simulator**: Vol.1で作成したPython Simulator (v1.2以上で障害物対応済)。
- **Config**: `config/experiment/obstacle_avoidance.yaml`

## 4. 実行コマンド
再現性を担保するため、`uv run` を用いた実行コマンドを記載します。

```bash
# 依存関係のインストール（初回のみ）
uv sync

# 障害物回避の学習パイプライン実行
# args: obs_type=obstacle, strategy=track_forward
# これにより、障害物ありの環境(Track Forward)でのデータ収集〜学習〜評価が自動実行されます
uv run experiment/scripts/run_mlops_pipeline.py \
    --obs_type obstacle \
    --strategy track_forward
```

## 5. 結果（結果概要）
- **完走率**: 学習モデルは教師アルゴリズムよりも高い成功率を記録。
- **滑らかさ (Jerk)**:
  - Teacher: 3.5 m/s^3 (平均) <!-- QUESTION: 実際の計測値を入れてください -->
  - Student (Model): **1.8 m/s^3** (平均) -> **約50%滑らかに！** <!-- QUESTION: 実際の計測値を入れてください -->
- **動画**: [回避成功シーンのGIF]

## 6. ログ詳細
- 比較評価ログ: `evaluation/results/v3_obstacle/comparison.json`
- 失敗シーンの分析 (Foxglove): [Link]

## 7. 考察
- **教師超えの理由**: Track Forwardによる高密度なデータ収集により、AIが教師の「下手な操作（カクつき）」を平均化・平滑化して学習した。
  - 大量のデータからの学習には、個々のサンプルのノイズ（教師のブレ）を相殺し、本質的な「回避の法則」を抽出する効果がある（Statistical Smoothing）。
- **シミュレータ内製化の勝利**: データ収集環境自体を自由にハックできる（Track Forwardを作るなど）ことが、E2E自動運転開発における最強の武器。
- 自作Pythonシミュレータ + MLOps環境により、アイデアを即座に実験・検証できるサイクルが完成した。

## 8. 参考文献 (References)
- [Behavioral Cloning for Autonomous Driving](https://arxiv.org/abs/...)
- [Curriculum Learning](https://...): Track Forwardは一種のカリキュラム学習とみなせる。
