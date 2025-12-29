import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def aggregate_results(root_dir: Path):
    """集計対象のディレクトリから全エピソードの結果を読み込む"""
    results = []

    # 複数ジョブ（Multirun）の出力を再帰的に探索
    for result_file in root_dir.rglob("result.json"):
        try:
            with open(result_file) as f:
                data = json.load(f)
                # ジョブIDやパスの一部を記録
                data["path"] = str(result_file.parent)
                results.append(data)
        except Exception as e:
            print(f"Error reading {result_file}: {e}", file=sys.stderr)

    if not results:
        print("No results found.")
        return None

    df = pd.json_normalize(results)
    return df


def show_summary(df: pd.DataFrame):
    """集計結果をコンソールに表示"""
    print("\n" + "=" * 50)
    print("      AGGREGATED SIMULATION RESULTS")
    print("=" * 50)

    total = len(df)
    success = df["success"].sum()
    success_rate = (success / total) * 100 if total > 0 else 0

    print(f"Total Episodes:  {total}")
    print(f"Success Count:   {success}")
    print(f"Success Rate:    {success_rate:.2f}%")

    if "reason" in df.columns:
        print("\nFailure Reasons Breakdown:")
        reasons = df[~df["success"]]["reason"].value_counts()
        for reason, count in reasons.items():
            print(f"  - {reason}: {count}")

    if any(col.startswith("metrics.") for col in df.columns):
        print("\nMetrics Summary (Mean):")
        metrics_cols = [col for col in df.columns if col.startswith("metrics.")]
        for col in metrics_cols:
            print(f"  - {col.replace('metrics.', '')}: {df[col].mean():.2f}")

    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate simulation results from multiple episodes."
    )
    parser.add_argument(
        "dir",
        type=str,
        nargs="?",
        help="Directory to search for result.json files. Defaults to 'outputs/latest' or the most recent run.",
    )
    args = parser.parse_args()

    if args.dir:
        root_path = Path(args.dir)
    else:
        # try 'outputs/latest' first
        latest_symlink = Path("outputs/latest")
        if latest_symlink.exists():
            root_path = latest_symlink
            print(f"Using latest results from: {root_path.resolve()}")
        else:
            # automatic discovery
            outputs_dir = Path("outputs")
            if not outputs_dir.exists():
                print("No 'outputs' directory found.")
                sys.exit(1)

            # Find all dated subdirectories (assumes format outputs/YYYY-MM-DD/HH-MM-SS)
            # We look for 2 levels deep
            candidates = sorted(outputs_dir.glob("*/*"))
            candidates = [p for p in candidates if p.is_dir()]

            if not candidates:
                print("No result directories found in 'outputs/'.")
                sys.exit(1)

            root_path = candidates[-1]
            print(f"Using most recent results found: {root_path}")

    if not root_path.exists():
        print(f"Directory not found: {root_path}")
        sys.exit(1)

    df = aggregate_results(root_path)
    if df is not None:
        show_summary(df)

        # Save aggregated CSV
        csv_path = root_path / "aggregated_results.csv"
        df.to_csv(csv_path, index=False)
        print(f"Saved aggregated results to {csv_path}")


if __name__ == "__main__":
    main()
