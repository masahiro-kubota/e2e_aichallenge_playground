#!/usr/bin/env bash
# 障害物エディターを起動するスクリプト

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "🚀 障害物エディターを起動しています..."

# フロントエンドの依存関係をインストール（初回のみ）
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "📦 フロントエンドの依存関係をインストール中..."
    cd "$FRONTEND_DIR"
    npm install
    cd "$SCRIPT_DIR"
fi

# バックエンドとフロントエンドを並行起動
echo "🔧 バックエンドとフロントエンドを起動中..."

# バックエンドを起動（バックグラウンド）
uv run python obstacle_editor_server.py &
BACKEND_PID=$!

# フロントエンドを起動（バックグラウンド）
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

# 終了時のクリーンアップ
cleanup() {
    echo ""
    echo "🛑 サーバーを停止しています..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

echo ""
echo "✅ 起動完了！"
echo ""
echo "📍 ブラウザで以下のURLにアクセスしてください："
echo "   http://localhost:5173"
echo ""
echo "💡 停止するには Ctrl+C を押してください"
echo ""

# サーバーが起動するまで待機
sleep 3

# ブラウザを自動で開く（オプション）
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:5173 2>/dev/null || true
elif command -v open > /dev/null; then
    open http://localhost:5173 2>/dev/null || true
fi

# プロセスが終了するまで待機
wait
