# TinyLidarNet: 2D LiDAR-based End-to-End Deep Learning Model for F1TENTH Autonomous Racing
各章の要約まとめ

## Abstract
F1TENTH（1/10スケール自律走行レース）において、2D LiDARのみを入力とする軽量なEnd-to-Endモデル「TinyLidarNet」を提案。第12回F1TENTH Grand Prixで3位に入賞した。
画像処理で実績のあるCNN（畳み込みニューラルネットワーク）を1D LiDARデータに応用し、従来のMLP（多層パーセプトロン）手法と比較して、高速走行時の性能や未知環境への汎化性能が大幅に向上したことを示した。また、ESP32などの安価なマイコンでもリアルタイム動作可能なほど軽量である。

## I. Introduction
自律走行レースでは、高速な意思決定と計算効率の両立が求められる。従来の「認知・計画・制御」のパイプライン型は計算コストが高く、誤差が蓄積しやすい。
End-to-End学習は有望だが、カメラ画像はデータ量が大きく、従来の2D LiDAR x MLP手法は性能に限界があった。
本研究では、1D CNNを用いたTinyLidarNetを開発。以下の点を明らかにする：
1. F1TENTHレースで通用する競争力があるか？
2. どの程度の計算リソースが必要か？（マイコンで動くか？）
3. 未知のコースでも再学習なしで走れるか？（汎化性能は？）

## II. Background and Related Work
- **F1TENTH**: 1/10スケールのラジコンカーを用いた自律走行コンペティション。2D LiDARが主センサ。
- **End-to-End**: 入力から制御出力を直接学習する手法。ALVINN(1989)やNVIDIA DAVE-2(2016, PilotNet)など画像ベースが有名。
- **課題**: F1TENTHにおける従来のEnd-to-EndはMLPベースが主流だったが、速度が出ない、蛇行する、汎化しないといった問題があり、実戦では敬遠されていた。本研究はこれを覆すものである。

## III. F1TENTH Platform and 2D LiDAR
- **車体**: Traxxas Rally 1/10シャーシ。
- **センサ**: Hokuyo UST-10LX 2D LiDAR（視野角270度、1081点、40Hz）。
- **計算機**: NVIDIA Jetson Xavier NX。
- **入力**: 1081点の距離データ（1D配列）。40Hzなので25ms以内に処理する必要がある。

## IV. TinyLidarNet
### A. Architecture
- NVIDIAの画像用モデル「PilotNet」に触発された構成。
- **1D CNN**: 入力が画像(2D)ではなくLiDAR(1D)なので、1次元畳み込み層を採用。
- **構成**: 9層（Conv x 5, FC x 4）。パラメータ数約22万。演算量(MACs)は約150万回と非常に軽量。

### B. Data Collection, Pre-processing and Training
- **データ収集**: ジョイスティックによる手動運転で収集。約5分間、12,329サンプル。
- **特徴**: 動的な障害物（他車）が存在する環境で収集した。
- **前処理**: 中央値フィルタ等でLiDARのノイズを除去。

## V. Evaluation
### 比較条件
- **データセット**: 全てのモデル（TinyLidarNet, MLP）は、Section IV-Bで記述された**同一のデータセット（F1TENTH大会で手動収集されたもの）**を使用して学習された。したがって、データ収集方法の違いによる比較ではない。純粋にネットワーク構造（1D CNN vs MLP）の違いによる性能差を検証している。
- **比較対象**:
  - TinyLidarNet (L/M/S): 入力次元数 1081/541/270
  - MLP256 (L/M/S): 入力次元数 1081/541/270, 隠れ層2層(各256ノード)

### A. Insights from an F1TENTH Competition
- 第12回大会で3位入賞。
- 衝突によりコース形状が変化しても対応できた（地図不要の強み）。
- 教師データには「静的な障害物」しか含まれていないにも関わらず、レース中に動く他車を追い抜くことができた（高い汎化性能）。
  - 他のチームは直線の長い区間でしか追い越しを行わなかったが、TinyLidarNetはトラックの**あらゆる場所**で追い越しに成功した。
  - これは、モデルが動いている車を「静的な障害物や壁」として認識し、適切に回避行動をとれたためと考えられる。

### B. Performance on Simulated Tracks
- 4つの異なるシミュレーションコース (GYM, Austin, Moscow, Spielberg) で検証。
- **TinyLidarNet**: 全てのコースで完走率100%（平均進捗100%）。Lap Timeも良好で安定している。
- **MLP256**: 一部のコース(GYM)では完走できるが、未知のコース(Austinなど)では平均進捗率が16%〜48%と低く、完走できないケースが多い。
- **考察**: MLPは空間的な特徴を捉えられないため、未知のコースに適応できない。一方、TinyLidarNetの1D CNNはLiDAR点群の空間的特徴を捉えるため汎化性能が高い。

### C. Inference Latency
- **Jetson Xavier NX**: 1ms未満 (fp32/int8)。
- **ESP32-S3 (マイコン)**: float32では838msだが、int8量子化を行うことで**16ms (>50Hz)**で動作可能。
- **Raspberry Pi Pico**: int8量子化で36ms (>20Hz)。
- 結論：マイコンでも十分実用的な速度で動作する。

### D. Performance on Unseen Real Tracks
- 学習データに含まれない、研究室に設置した未知の実環境コースで検証（Simulation to Realityではなく、実データで学習して別の実環境でテストするReal to Realに近い構成）。
- **TinyLidarNet**: L, Mモデルは5回中5回完走 (**成功率100%**)。Sモデルは80%。
- **MLP256**: 全モデルが5回中5回ともクラッシュ (**成功率0%**)。
- 実環境においても1D CNNの優位性と高い汎化性能が確認された。

## VI. Conclusion
- TinyLidarNetを提案し、その有効性を実証した。
- 1D CNNアーキテクチャは、従来のMLPよりも2D LiDARデータの処理において優れている。
- 量子化により超低コストなマイコンでも動作可能。
- 今後はDAgger等の学習手法や強化学習への応用を検討する。
