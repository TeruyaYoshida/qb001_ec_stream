# QB EC Stream - 中古衣料品販売自動化システム

Yahoo!オークション出品、佐川急便発送登録、再出品を自動化するデスクトップアプリケーション。

## 概要

QB EC Streamは、中古衣料品のオンライン販売業務を効率化するPython製デスクトップアプリケーションです。

### 主な機能

- **📧 Gmail連携**: 出品依頼メールを自動解析して出品データを生成
- **🌐 ブラウザ自動化**: Playwrightを使用したYahoo!オークション・佐川急便Webサイトの自動操作
- **🔄 再出品機能**: 落札されなかった商品を自動で再出品
- **📦 重複防止**: 発送済みオークションIDを記録し、重複処理を防止
- **📝 詳細ログ**: JSON Lines形式でのイベントログ記録

## システム要件

- **OS**: Windows 10/11, macOS 11+
- **Python**: 3.12以上
- **ブラウザ**: Google Chrome（ユーザープロファイルを使用）
- **外部API**: Gmail API（認証情報が必要）

## クイックスタート

### 1. インストール

```bash
# リポジトリのクローン
git clone https://github.com/your-org/qb001_ec_stream.git
cd qb001_ec_stream

# uvで依存関係をインストール（推奨）
uv sync

# Playwrightブラウザのインストール
uv run playwright install chromium
```

### 2. 設定ファイルの準備

#### Gmail API認証情報の取得

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成
3. Gmail API を有効化
4. OAuth 2.0 クライアントID を作成（アプリケーションの種類: デスクトップ）
5. `credentials.json` をダウンロードして `config/` に配置

#### 設定ファイルの編集

`config/settings.json` を作成:

```json
{
  "chrome_profile_path": "/Users/username/Library/Application Support/Google/Chrome",
  "gmail_credentials_path": "config/credentials.json",
  "default_auction_duration": 7,
  "auto_relist": true,
  "log_level": "INFO"
}
```

**Chromeプロファイルパス:**
- **macOS**: `/Users/username/Library/Application Support/Google/Chrome`
- **Windows**: `C:\Users\username\AppData\Local\Google\Chrome\User Data`

### 3. アプリケーションの起動

```bash
uv run python src/main.py
```

GUIが起動し、3つのボタンが表示されます:

- **出品開始**: Gmail から出品依頼メールを取得し、Yahoo!オークションに自動出品
- **発送登録**: 落札通知メールから情報を抽出し、佐川急便に発送登録
- **再出品**: 落札されなかった商品を自動で再出品

## テスト

### ユニットテスト（全49テスト）

```bash
# すべてのテストを実行
uv run pytest

# 詳細表示
uv run pytest -v

# 特定のテストファイルのみ実行
uv run pytest tests/test_text_parser.py
```

### 統合テスト

```bash
# Gmail API認証テスト
uv run python tests/integration/test_gmail_auth.py

# ブラウザ起動テスト（Chromeを閉じてから実行）
uv run python tests/integration/test_browser_launch.py
```

### E2Eテスト

詳細は [E2Eテストガイド](docs/e2e_testing_guide.md) を参照してください。

## ビルド（実行ファイル作成）

### macOS / Linux

```bash
./build.sh
```

実行ファイルは `dist/qb001_ec_stream.app` に生成されます。

### Windows

```cmd
build.bat
```

実行ファイルは `dist/qb001_ec_stream.exe` に生成されます。

## プロジェクト構造

```
qb001_ec_stream/
├── src/
│   ├── main.py              # Flet GUI、メインエントリーポイント
│   ├── config.py            # 設定管理
│   ├── models/
│   │   └── item.py          # データモデル（ListingItem, ShippingRecord）
│   ├── services/
│   │   ├── gmail_service.py # Gmail API操作
│   │   ├── browser_service.py # Playwrightブラウザ管理
│   │   ├── auction_service.py # Yahoo!オークション自動化
│   │   └── shipping_service.py # 佐川急便発送登録
│   └── utils/
│       ├── logger.py        # ログ管理
│       ├── text_parser.py   # メール解析
│       └── file_manager.py  # ファイル・履歴管理
├── tests/
│   ├── test_*.py            # ユニットテスト（49テスト）
│   └── integration/         # 統合テスト
├── config/
│   ├── settings.json        # アプリ設定
│   └── credentials.json     # Gmail API認証情報（要配置）
├── data/
│   ├── images/              # 添付画像の保存先
│   └── history/             # 発送履歴
├── logs/                    # アプリケーションログ（JSON Lines形式）
└── docs/
    ├── system_specification.md  # システム仕様書
    ├── user_manual.md          # ユーザーマニュアル
    └── e2e_testing_guide.md    # E2Eテストガイド
```

## ドキュメント

- **[システム仕様書](docs/system_specification.md)**: 技術仕様、データフロー、エラーハンドリング
- **[ユーザーマニュアル](docs/user_manual.md)**: 初期設定、使い方、トラブルシューティング
- **[E2Eテストガイド](docs/e2e_testing_guide.md)**: 統合テスト・E2Eテストの実施手順
- **[AGENTS.md](AGENTS.md)**: 開発者向けコーディング規約・ガイドライン

## 技術スタック

| カテゴリ | 技術 | バージョン |
|---------|------|-----------|
| GUI | Flet | 0.21.2 |
| ブラウザ自動化 | Playwright (Sync API) | 1.41.0 |
| メール | Google API Client (Gmail API) | 2.111.0 |
| プロセス管理 | psutil | 5.9.7 |
| ビルド | PyInstaller | 6.18.0 |
| テスト | pytest | 9.0.2 |

## 開発ワークフロー

### コーディング規約

- **インポート順序**: 標準ライブラリ → サードパーティ → ローカルモジュール
- **命名規則**: `snake_case` (関数/変数), `PascalCase` (クラス), `UPPER_SNAKE` (定数)
- **型ヒント**: すべての関数に型アノテーションを使用
- **エラーハンドリング**:
  - 出品・再出品: スキップして継続
  - 発送: 即座に停止（誤配送防止）

### コミットメッセージ

Conventional Commits形式を使用:

```
feat: 新機能追加
fix: バグ修正
refactor: リファクタリング
docs: ドキュメント更新
test: テスト追加・修正
chore: ビルド・設定変更
```

## トラブルシューティング

### Chrome競合エラー

**症状:** "Chrome is already running" エラー

**解決策:**
1. すべてのChromeウィンドウを閉じる
2. タスクマネージャーでChromeプロセスを強制終了
3. アプリケーションを再起動

### Gmail API認証エラー

**症状:** "credentials.json not found"

**解決策:**
1. `config/credentials.json` が存在することを確認
2. 存在しない場合は Google Cloud Console から再ダウンロード
3. `config/token.json` を削除して再認証

### Playwright ブラウザエラー

**症状:** "Executable doesn't exist"

**解決策:**
```bash
uv run playwright install chromium
```

詳細は [ユーザーマニュアル](docs/user_manual.md) を参照してください。

## ライセンス

このプロジェクトは内部利用専用です。

## サポート

問題が発生した場合は、以下を確認してください:

1. **ログファイル**: `logs/app_YYYY-MM-DD.json`
2. **設定ファイル**: `config/settings.json`
3. **ドキュメント**: `docs/` 配下の各種ガイド

---

**開発者**: QB Development Team  
**最終更新**: 2026年1月30日
