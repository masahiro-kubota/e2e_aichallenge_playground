#!/usr/bin/env python3
"""experiment-runnerのプロファイリングヘルパースクリプト

py-spyを使ってexperiment-runnerの実行時間を計測し、
flamegraphまたはSpeedscope形式で出力します。
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="experiment-runnerをプロファイリング実行します")
    parser.add_argument(
        "--format",
        choices=["flamegraph", "speedscope"],
        default="speedscope",
        help="出力形式 (default: speedscope)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="出力ファイル名 (default: profile.{svg|speedscope.json})",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=1000,
        help="サンプリングレート (Hz) (default: 1000)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=1.0,
        help="シミュレーション実行時間 (sec) (default: 1.0)",
    )
    parser.add_argument(
        "--subprocesses",
        action="store_true",
        help="サブプロセスも含めてプロファイリング",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="C/C++拡張も含める (要root権限)",
    )

    args = parser.parse_args()

    # 出力ファイル名を決定
    if args.output:
        output_file = args.output
    else:
        if args.format == "speedscope":
            output_file = Path("profile.speedscope.json")
        else:
            output_file = Path("profile_flamegraph.svg")

    # py-spyコマンドを構築
    # uv run経由だとpy-spyがPythonプロセスを見つけられないため、
    # Pythonスクリプトを直接実行する
    cmd = [
        "py-spy",
        "record",
        "-o",
        str(output_file),
        "--rate",
        str(args.rate),
    ]

    if args.format == "speedscope":
        cmd.extend(["--format", "speedscope"])

    if args.subprocesses:
        cmd.append("--subprocesses")

    if args.native:
        cmd.append("--native")

    # experiment-runnerのエントリーポイントを直接実行
    # プロファイリング用に実行時間を短縮（1秒のみ）
    cmd.extend(
        [
            "--",
            "python",
            "-m",
            "experiment.cli",
            f"execution.duration_sec={args.duration}",
            "postprocess.dashboard.enabled=false",  # ダッシュボード生成を無効化
            "postprocess.mcap.enabled=false",  # MCAP出力を無効化
        ]
    )

    print(f"🔍 プロファイリング開始: {' '.join(cmd)}")
    print(f"📊 出力ファイル: {output_file.absolute()}")
    print()

    try:
        subprocess.run(cmd, check=False)
        print()

        if output_file.exists():
            print("✅ プロファイリング完了!")
            print(f"📁 結果: {output_file.absolute()}")
            print()

            if args.format == "speedscope":
                print("🌐 Speedscopeで表示を試みます...")
                try:
                    # speedscopeコマンドを実行
                    subprocess.run(["speedscope", str(output_file)], check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        print("🌐 speedscopeが見つかりません。npxで実行を試みます...")
                        subprocess.run(["npx", "speedscope", str(output_file)], check=True)
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        print("⚠️  speedscopeコマンドが見つからないか、実行に失敗しました。")
                        print("以下の手順でインストールしてローカルで起動できます：")
                        print("1. npm install -g speedscope")
                        print(f"2. speedscope {output_file}")
            else:
                print(f"🌐 ブラウザで {output_file.absolute()} を開いて確認してください。")

            return 0
        else:
            print("❌ エラー: プロファイルファイルが生成されませんでした")
            return 1

    except KeyboardInterrupt:
        print("\n⚠️  中断されました")
        return 130


if __name__ == "__main__":
    sys.exit(main())
