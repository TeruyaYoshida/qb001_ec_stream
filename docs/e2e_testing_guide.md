# エンドツーエンド (E2E) テストガイド

このドキュメントでは、QB EC Stream（中古衣料品販売自動化システム）のエンドツーエンドテスト手順を説明します。

## 目次

1. [事前準備](#事前準備)
2. [統合テスト](#統合テスト)
3. [E2Eテスト（出品ワークフロー）](#e2eテスト出品ワークフロー)
4. [E2Eテスト（発送ワークフロー）](#e2eテスト発送ワークフロー)
5. [E2Eテスト（再出品ワークフロー）](#e2eテスト再出品ワークフロー)
6. [ビルドテスト](#ビルドテスト)
7. [トラブルシューティング](#トラブルシューティング)

---

## 事前準備

### 1. 依存関係のインストール

```bash
# uvを使用（推奨）
uv sync --dev

# Playwrightブラウザのインストール
uv run playwright install chromium
```

### 2. 設定ファイルの準備

#### config/settings.json

```json
{
  "chrome_profile_path": "/Users/username/Library/Application Support/Google/Chrome",
  "gmail_credentials_path": "config/credentials.json",
  "default_auction_duration": 7,
  "auto_relist": true,
  "log_level": "INFO"
}
```

**重要:** Chromeプロファイルパスは環境に合わせて変更してください。

- **macOS**: `/Users/username/Library/Application Support/Google/Chrome`
- **Windows**: `C:\Users\username\AppData\Local\Google\Chrome\User Data`

#### config/credentials.json (Gmail API)

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成
3. Gmail API を有効化
4. OAuth 2.0 クライアント ID を作成（アプリケーションの種類: デスクトップ）
5. `credentials.json` をダウンロードして `config/` に配置

### 3. ユニットテストの実行

まず、ユニットテストがすべて成功することを確認します。

```bash
uv run pytest -v
```

**期待結果:** 49テストすべてがPASS

---

## 統合テスト

### Gmail API認証テスト

Gmail APIの認証フローをテストします。

```bash
uv run python tests/integration/test_gmail_auth.py
```

**手順:**

1. スクリプト実行後、ブラウザが自動的に開きます
2. Googleアカウントでログイン
3. アプリケーションへのアクセスを許可
4. `config/token.json` が生成されることを確認

**期待結果:**

```
=== Gmail API認証テスト ===

✓ 認証情報ファイル: /path/to/config/credentials.json
✓ 認証成功
✓ トークンファイル生成: /path/to/config/token.json

未読メールの取得テスト...
✓ 未読メール取得成功: 5件

=== すべてのテストが成功しました ===
```

### ブラウザ起動テスト

Playwrightブラウザの起動と基本操作をテストします。

**注意:** Chromeを閉じてから実行してください。

```bash
uv run python tests/integration/test_browser_launch.py
```

**期待結果:**

```
=== Chrome競合検出テスト ===

検出結果: Chrome は起動していません
✓ check_chrome_running() = False

==================================================

=== Playwright ブラウザ起動テスト ===

Chromeプロファイル: /Users/username/Library/Application Support/Google/Chrome
✓ Chrome競合なし
✓ ブラウザコンテキスト起動成功
✓ 新しいページ作成成功
✓ ページタイトル: Yahoo! JAPAN
✓ スクリーンショット保存: /path/to/logs/browser_test.png

=== すべてのテストが成功しました ===
```

---

## E2Eテスト（出品ワークフロー）

実際のGmailとYahoo!オークションを使用して出品ワークフローをテストします。

### 準備

1. テスト用Gmailアカウントに出品依頼メールを送信

**メール例:**

```
件名: 出品依頼

【商品名】ヴィンテージデニムジャケット
【価格】5000
【商品説明】1990年代のヴィンテージデニムジャケット。サイズM。
【商品状態】目立った傷や汚れなし
【オークション期間】7
【カテゴリ】23336
【添付】jacket_front.jpg, jacket_back.jpg
```

### テスト手順

1. アプリケーションを起動

```bash
uv run python src/main.py
```

2. GUIで「出品開始」ボタンをクリック

3. 以下の動作を確認:
   - Gmail から未読メールを取得
   - メール本文を解析して `ListingItem` を生成
   - 添付画像を `data/images/` に保存
   - Yahoo!オークションにログイン（ブラウザが開く）
   - 出品フォームに自動入力
   - 画像をアップロード
   - 出品を完了
   - Gmailに「出品済み」ラベルを付与

4. Yahoo!オークションにアクセスして出品が完了していることを確認

### 期待結果

- ログファイル `logs/app_YYYY-MM-DD.json` に処理履歴が記録される
- 出品が正常に完了し、オークションIDが取得できる
- Gmailのメールに「出品済み」ラベルが付与される

---

## E2Eテスト（発送ワークフロー）

落札後の発送登録ワークフローをテストします。

### 準備

1. テスト用Gmailアカウントに落札通知メールを送信（Yahoo!オークションからの実際の通知を使用）

### テスト手順

1. アプリケーションを起動

```bash
uv run python src/main.py
```

2. GUIで「発送登録」ボタンをクリック

3. 以下の動作を確認:
   - Gmail から落札通知メールを取得
   - メールから落札情報（オークションID、落札者情報）を抽出
   - 既に発送済みのIDは `data/history/shipped_ids.json` でスキップ
   - 佐川急便のWebサイトにアクセス（ブラウザが開く）
   - 発送登録フォームに自動入力
   - 登録完了後、オークションIDを履歴に保存

### 期待結果

- 発送登録が正常に完了する
- `data/history/shipped_ids.json` にオークションIDが記録される
- 同じIDは2回処理されない（重複防止）

---

## E2Eテスト（再出品ワークフロー）

落札されなかった商品の再出品ワークフローをテストします。

### テスト手順

1. Yahoo!オークションで終了したオークション（落札なし）を用意

2. アプリケーションを起動

```bash
uv run python src/main.py
```

3. GUIで「再出品」ボタンをクリック

4. 以下の動作を確認:
   - Yahoo!オークションにアクセス
   - 終了オークション一覧から落札なしの商品を検出
   - 元のオークション情報（タイトル、価格、画像）を取得
   - 新しいオークションとして再出品

### 期待結果

- 再出品が正常に完了する
- 新しいオークションIDが取得できる
- 元の商品情報が正しく引き継がれている

---

## ビルドテスト

実行ファイル（.app / .exe）のビルドと動作をテストします。

### macOS

```bash
# ビルド
./build.sh

# ビルド成果物の確認
ls -lh dist/

# アプリケーションの起動
open dist/qb001_ec_stream.app
```

### Windows

```cmd
REM ビルド
build.bat

REM 実行ファイルの起動
dist\qb001_ec_stream.exe
```

### ビルド確認項目

- [ ] アプリケーションが正常に起動する
- [ ] 設定ファイルが正しく読み込まれる
- [ ] Gmail API認証が機能する
- [ ] ブラウザ自動化が機能する
- [ ] すべてのワークフロー（出品・発送・再出品）が正常に動作する

---

## トラブルシューティング

### Chrome競合エラー

**エラー:** `Chrome is already running`

**解決策:**

1. すべてのChromeウィンドウを閉じる
2. タスクマネージャー（Activity Monitor）でChromeプロセスを強制終了
3. アプリケーションを再起動

### Gmail API認証エラー

**エラー:** `credentials.json not found`

**解決策:**

1. Google Cloud Consoleで `credentials.json` を再ダウンロード
2. `config/credentials.json` に配置
3. `config/token.json` を削除して再認証

### Playwright インストールエラー

**エラー:** `Executable doesn't exist at /path/to/chromium`

**解決策:**

```bash
# Chromiumブラウザを手動インストール
uv run playwright install chromium

# すべてのブラウザをインストール
uv run playwright install
```

### 画像アップロードエラー

**エラー:** 画像が見つからない

**解決策:**

1. メールの添付ファイルが正しく保存されているか確認: `data/images/`
2. ファイル名に特殊文字が含まれていないか確認
3. 画像形式がサポートされているか確認（JPG, PNG, GIF）

### ログファイルの確認

問題が発生した場合は、ログファイルを確認してください。

```bash
# 最新のログファイルを表示
tail -f logs/app_$(date +%Y-%m-%d).json

# ログをJSON整形して表示（jqを使用）
cat logs/app_$(date +%Y-%m-%d).json | jq .
```

---

## テスト完了チェックリスト

### ユニットテスト
- [ ] すべてのユニットテストがPASS (49/49)

### 統合テスト
- [ ] Gmail API認証が成功
- [ ] ブラウザ起動が成功
- [ ] Chrome競合検出が機能

### E2Eテスト
- [ ] 出品ワークフローが正常に完了
- [ ] 発送ワークフローが正常に完了
- [ ] 再出品ワークフローが正常に完了
- [ ] 重複防止機能が動作

### ビルドテスト
- [ ] PyInstallerビルドが成功
- [ ] 実行ファイルが正常に起動
- [ ] すべての機能が動作

---

## 次のステップ

テストがすべて成功したら:

1. **本番環境への展開**
   - 本番用Gmailアカウントを設定
   - 本番用Yahoo!オークションアカウントでテスト

2. **継続的インテグレーション (CI) の設定**
   - GitHub Actions でユニットテストを自動実行
   - コードカバレッジレポートの生成

3. **ユーザードキュメントの整備**
   - スクリーンショット付きの詳細マニュアル作成
   - FAQ の充実

4. **パフォーマンス最適化**
   - 大量メール処理時の性能測定
   - ブラウザ操作の高速化

---

## 参考資料

- [システム仕様書](system_specification.md)
- [ユーザーマニュアル](user_manual.md)
- [AGENTS.md](../AGENTS.md) - 開発者向けガイドライン
