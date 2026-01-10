# 【爆速シミュレータ】Unity挙動をPythonで完全再現してみた

## 0. TL;DR
- **What**: AWSIM (Unity) の挙動を再現するPython製プロキシ・シミュレータを開発した。
- **Result**: 実時間比で **100倍以上** の高速化を実現し、ステアリング応答もUnityと一致させた。
- **So What**: これにより、数万エピソード規模の大規模強化学習/模倣学習が可能になった。

---

## 1. 目的（問題意識・課題感）
- **What**: End-to-End自動運転の学習環境において、実時間比で100倍以上の高速化を実現したい。
- **Why**:
  - AWSIM + Autowareは素晴らしいが、大規模学習（数万エピソード）には計算コストと時間がかかりすぎる。
  - プログラムからの制御（初期位置や障害物の自由な配置）に制約があり、エッジケースの効率的な収集が難しい。
- **Goal**: 学習に特化した軽量かつ高精度なPython製プロキシ・シミュレータを構築し、MLOpsの基盤とする。

## 2. 実験設定（解決策・作ったもの）
### Approach Selection (アプローチの選定理由)
<!-- QUESTION: ここが一番重要です。なぜ以下の選択肢ではなく、今回のPythonシミュレータ自作を選んだのですか？ -->
- **Alternatives**:
  - AWSIM (Unity) をそのまま高速化する（TimeScaleを変えるなど）。
  - CARLAやAirSimなど他の既存シミュレータを使う。
- **Reason**:
  - <!-- ANSWER: ここに理由を書いてください。例：Unityのオーバーヘッドが大きすぎて100倍は無理だった、Pythonの資産（Gymなど）を使いたかった、etc -->

### Proposed Method: Python Proxy Simulator with FOPDT
AWSIMの物理挙動を模倣するPythonシミュレータを作成しました。
単なるキネマティックモデルではなく、システム同定によりUnity特有の「遅れ」や「慣性」まで再現しています。

- **ステアリング応答**: 無駄時間＋1次遅れ系 (FOPDT) モデルを採用。
  - 実環境（Unity）のステップ応答データから、時定数 $\tau$ と無駄時間 $L$ を同定。
- **縦方向ダイナミクス**: 空気抵抗とコーナリングドラッグを考慮。
- **アーキテクチャ**: Gymライクなインターフェース、Headless動作。

### Experiment Setup: ベンチマーク条件
- **比較対象**: オリジナルのAWSIM (Unityバイナリ) 環境。
- **Model Parameters**:
    - Steer Delay (L): 0.1s <!-- QUESTION: この値は正確ですか？ -->
    - Time Constant (tau): 0.15s <!-- QUESTION: この値は正確ですか？ -->
    - (同定された具体的な値を記載) <!-- QUESTION: 他に重要なパラメータがあれば追記してください -->

### Metrics (評価指標)
- **波形一致度**: Unityの実測値とシミュレータ出力の二乗平均平方根誤差 (RMSE)。
- **Execution Speed (xRT)**: 実時間に対する処理速度倍率 (Real-Time Factor)。

## 3. 前提環境 (Prerequisites)
- **OS**: Ubuntu 24.04
- **Python**: 3.10
- **Dependencies**: Managed by `uv`
- **Machine**: Intel Core i9-13900K, 64GB RAM (GPU不要)

## 4. 実行コマンド
再現性を担保するため、`uv run` を用いた実行コマンドを記載します。

```bash
# 1. 依存関係のインストール
uv sync

# 2. システム同定 (UnityのMCAPログからパラメータを推定)
# args: input_mcap, config_yaml
uv run scripts/system_identification/estimate_dynamics.py train \
    data/system_id/unity_log.mcap \
    experiment/conf/vehicle/default.yaml

# 3. シミュレータのベンチマーク実行 (100回試行)
uv run simulator/benchmarks/benchmark_lidar.py --iterations 100
```

## 5. 結果（結果概要）
- **速度**: 実時間比で**100倍以上**の高速化を確認。1時間の走行データなら数分で収集可能。
- **挙動再現性**:
  - ステアリングの遅れ（指令から実際の動き出しまでのタイムラグ）がUnityとほぼ一致。
  - 高速旋回時の減速感も再現されており、Sim-to-Sim転移の可能性が高まった。

## 6. ログ詳細
- システム同定に使用したMCAPデータ: `data/system_id/unity_log.mcap`
- ベンチマークログ: `vmstat_benchmark.log`

## 7. 考察
- キネマティックモデルにFOPDT要素（遅れ）を加えるだけで、Unityの挙動に劇的に近づいた。
- これにより、Python側で学習したモデルをUnityに戻しても、制御崩壊を起こさずに走行できる可能性が高い。
- 今後は、この「爆速環境」を使って実際に強化学習/模倣学習のサイクルを回していく（Vol.2へ続く）。

## 8. 参考文献 (References)
- [AWSIM Documentation](https://tier4.github.io/AWSIM/)
- [Autoware Universe](https://github.com/autowarefoundation/autoware.universe)
