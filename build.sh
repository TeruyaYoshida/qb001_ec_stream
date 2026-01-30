#!/usr/bin/env bash
# ビルドスクリプト - PyInstallerで実行ファイルを作成

set -e  # エラー時に停止

echo "=== QB EC Stream ビルドスクリプト ==="
echo ""

# カレントディレクトリの確認
if [ ! -f "pyproject.toml" ]; then
    echo "エラー: pyproject.tomlが見つかりません。プロジェクトルートで実行してください。"
    exit 1
fi

# 依存関係のインストール確認
echo "1. 依存関係の確認..."
uv sync --dev

# テストの実行
echo ""
echo "2. テストの実行..."
uv run pytest -v

# ビルドディレクトリのクリーンアップ
echo ""
echo "3. 前回のビルド成果物をクリーンアップ..."
rm -rf build/ dist/ __pycache__/

# PyInstallerでビルド
echo ""
echo "4. PyInstallerでビルド中..."
uv run pyinstaller qb001_ec_stream.spec

# ビルド結果の確認
echo ""
echo "=== ビルド完了 ==="
if [ -d "dist/qb001_ec_stream.app" ]; then
    echo "macOS App Bundle: dist/qb001_ec_stream.app"
    echo ""
    echo "実行方法:"
    echo "  open dist/qb001_ec_stream.app"
elif [ -f "dist/qb001_ec_stream" ]; then
    echo "実行ファイル: dist/qb001_ec_stream"
    echo ""
    echo "実行方法:"
    echo "  ./dist/qb001_ec_stream"
else
    echo "警告: ビルド成果物が見つかりません。"
    exit 1
fi

echo ""
echo "注意事項:"
echo "- 初回起動時は設定ファイル (config/settings.json) の編集が必要です"
echo "- Gmail API認証情報 (config/credentials.json) を配置してください"
echo "- Playwrightブラウザが必要な場合は手動でインストールしてください"
