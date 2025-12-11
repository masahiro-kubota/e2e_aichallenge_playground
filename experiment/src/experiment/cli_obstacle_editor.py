"""CLI tool to launch the obstacle editor."""

import contextlib
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def kill_process_on_port(port: int) -> None:
    """Kill any process using the specified port."""
    try:
        # Find process using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    time.sleep(0.5)
                except (ProcessLookupError, ValueError):
                    pass
    except FileNotFoundError:
        # lsof not available, skip
        pass


def main() -> None:
    """Start the obstacle editor (backend + frontend)."""
    # Get the project root (e2e_aichallenge_playground)
    # This file is in experiment/src/experiment/cli_obstacle_editor.py
    project_root = Path(__file__).parent.parent.parent.parent
    tools_dir = project_root / "experiment" / "tools"
    frontend_dir = tools_dir / "frontend"

    print("🚀 障害物エディターを起動しています...")

    # Kill any existing processes on port 8000
    kill_process_on_port(8000)

    # Check if frontend dependencies are installed
    if not (frontend_dir / "node_modules").exists():
        print("📦 フロントエンドの依存関係をインストール中...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)

    print("🔧 バックエンドとフロントエンドを起動中...")

    # Start backend
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "obstacle_editor_server:app", "--host", "0.0.0.0"],
        cwd=tools_dir,
    )

    # Start frontend
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
    )

    print()
    print("✅ 起動完了!")
    print()
    print("📍 ブラウザで以下のURLにアクセスしてください:")
    print("   http://localhost:5173")
    print()
    print("💡 停止するには Ctrl+C を押してください")
    print()

    # Wait a bit for servers to start
    time.sleep(3)

    # Open browser
    with contextlib.suppress(Exception):
        webbrowser.open("http://localhost:5173")

    # Wait for processes
    try:
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print()
        print("🛑 サーバーを停止しています...")
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait()
        frontend_process.wait()
        print("✅ 停止しました")


if __name__ == "__main__":
    main()
