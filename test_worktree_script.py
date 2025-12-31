#!/usr/bin/env python3
"""
ワークツリーテストスクリプト
このスクリプトはワークツリー内でのみ存在し、メインの作業環境には影響しません。
"""

import os
import sys
from pathlib import Path


def main():
    print("=" * 60)
    print("ワークツリーテストスクリプト")
    print("=" * 60)
    
    # 現在のディレクトリ情報を表示
    current_dir = Path.cwd()
    print(f"\n現在のディレクトリ: {current_dir}")
    print(f"スクリプトの場所: {Path(__file__).parent}")
    
    # Gitブランチ情報を取得
    try:
        import subprocess
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=current_dir,
            text=True
        ).strip()
        print(f"現在のブランチ: {branch}")
    except Exception as e:
        print(f"ブランチ情報取得エラー: {e}")
    
    # ワークツリー一覧を表示
    try:
        worktrees = subprocess.check_output(
            ["git", "worktree", "list"],
            cwd=current_dir,
            text=True
        )
        print(f"\nワークツリー一覧:")
        print(worktrees)
    except Exception as e:
        print(f"ワークツリー情報取得エラー: {e}")
    
    # 簡単な計算テスト
    print("\n簡単な計算テスト:")
    result = sum(range(1, 101))
    print(f"1から100までの合計: {result}")
    
    print("\n" + "=" * 60)
    print("テスト完了! このスクリプトはワークツリー内でのみ動作します。")
    print("=" * 60)


if __name__ == "__main__":
    main()
