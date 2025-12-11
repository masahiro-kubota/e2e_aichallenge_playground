# 障害物エディター

ブラウザベースの障害物編集ツールです。YAMLファイルを読み込んで、地図上で障害物を視覚的に配置できます。

## 機能

- YAMLファイルから障害物設定を読み込み
- Lanelet2マップ（OSM形式）の表示
- 障害物の視覚的な配置（ドラッグ&ドロップ）
- 障害物の追加・編集・削除
- 矩形と円形の障害物をサポート
- 座標・サイズ・回転角の直接入力
- YAMLファイルへの保存

## 使い方

### 🚀 最も簡単な起動方法（推奨）

プロジェクトルートから以下のコマンド一つで起動できます：

```bash
uv run obstacle-editor
```

これにより：
1. フロントエンドの依存関係を自動インストール（初回のみ）
2. バックエンド（FastAPI）とフロントエンド（Vite）を同時起動
3. ブラウザが自動的に開きます（`http://localhost:5173`）

停止するには `Ctrl+C` を押してください。

### 🔧 スクリプトでの起動

または、ツールディレクトリに移動して起動スクリプトを使用：

```bash
cd experiment/tools
./start_editor.sh
```

---

### 📝 障害物の編集

1. ブラウザで `http://localhost:5173` にアクセス（自動で開きます）
2. YAMLファイルパスを入力（デフォルト: `experiment/configs/modules/default_module.yaml`）
3. 「読み込み」ボタンをクリック
4. 地図と既存の障害物が表示されます

### 🎮 操作方法

- **障害物の追加**: 「➕ 矩形を追加」または「⭕ 円形を追加」ボタンをクリック
- **障害物の選択**: 障害物をクリック
- **障害物の移動**: 選択した障害物をドラッグ
- **障害物の編集**: 右側のプロパティパネルで値を変更
- **障害物の削除**: 障害物を選択して「🗑️ 削除」ボタンをクリック
- **地図のパン**: Ctrlキーを押しながらドラッグ、または中クリックでドラッグ
- **地図のズーム**: マウスホイールでズーム
- **保存**: 「💾 保存」ボタンをクリックしてYAMLファイルに保存

---

## 詳細な起動方法（手動）

個別にサーバーを起動したい場合：

### バックエンド（FastAPI）

```bash
cd /home/masa/e2e_aichallenge_playground/experiment/tools
uv run python obstacle_editor_server.py
```

バックエンドサーバーが `http://localhost:8000` で起動します。

### フロントエンド（Vite + React）

別のターミナルで：

```bash
cd /home/masa/e2e_aichallenge_playground/experiment/tools/frontend
npm install  # 初回のみ
npm run dev
```

フロントエンドが `http://localhost:5173` で起動します。

---

## YAMLファイルの要件

編集対象のYAMLファイルは以下の構造を持つ必要があります：

```yaml
module:
  nodes:
    - name: "Simulator"
      params:
        map_path: "path/to/lanelet2_map.osm"  # 地図ファイルのパス
        obstacles:  # 障害物リスト
          - type: "static"
            shape:
              type: "rectangle"
              width: 2.0
              length: 4.0
            position:
              x: 89645.0
              y: 43132.0
              yaw: 0.0
```

## 技術スタック

- **バックエンド**: FastAPI, Python 3.12+
- **フロントエンド**: Vite, React 19, TypeScript
- **地図処理**: Lanelet2 OSM形式
- **YAML処理**: PyYAML

## トラブルシューティング

### ポートが既に使用されている

別のポートを使用する場合：

```bash
# バックエンド
uvicorn obstacle_editor_server:app --host 0.0.0.0 --port 8001

# フロントエンド
npm run dev -- --port 5174
```

フロントエンドのポートを変更した場合は、`vite.config.ts`のプロキシ設定も更新してください。

### 地図が表示されない

- YAMLファイルの`map_path`が正しいか確認
- OSMファイルが存在するか確認
- ブラウザのコンソールでエラーメッセージを確認

### npm installが失敗する

Node.jsのバージョンを確認してください（推奨: v20.19.0以上）：

```bash
node --version
```
