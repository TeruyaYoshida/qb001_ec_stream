# システム詳細仕様書（実装計画詳細版） - 中古衣料品販売自動化システム

> **初期リリーススコープ:** 本書は初期リリース（v1.0）の仕様を定義する。ECサイトは**ヤフオク!のみ**を対象とし、Yahoo!ショッピング対応は将来バージョン（v2.0以降）で実装予定。

## 1. システム基本仕様

| 項目 | 内容 |
| :--- | :--- |
| **OS** | Windows 10/11, macOS |
| **言語** | Python 3.10 以上 |
| **GUIフレームワーク** | Flet (`flet==0.21.2`) ※代替として Tkinter も利用可能 |
| **並行処理** | `threading` モジュールによるGUI非同期更新に対応 |
| **ブラウザ自動化** | Playwright (Python版 / Sync API) |
| **メール連携** | Google API Client (Gmail API) |
| **ログ管理** | ローカルファイル（JSON形式）、DB移行考慮設計 |
| **配布形式** | PyInstallerによる単体実行ファイル (.exe / .app) |

### 1.1 依存ライブラリ一覧

依存ライブラリは `requirements.txt` で管理する（詳細は Section 5.1 参照）。

---

## 2. ディレクトリ・モジュール詳細設計

```text
qb001_ec_stream/
├── src/
│   ├── main.py                # GUI構築・イベントハンドリング(スレッド制御)
│   ├── config.py              # 設定・パス解決(exe対応)
│   ├── models/
│   │   └── item.py            # データ定義
│   ├── services/
│   │   ├── gmail_service.py   # Gmail操作
│   │   ├── browser_service.py # ブラウザ起動管理・プロセスチェック
│   │   ├── auction_service.py # ヤフオク/Yahoo!ショッピング出品・再出品ロジック
│   │   └── shipping_service.py# 佐川発送ロジック・重複防止
│   └── utils/
│       ├── logger.py          # ログ基盤
│       ├── text_parser.py     # 解析ロジック
│       └── file_manager.py    # 画像掃除・ファイル操作・発送履歴管理
├── config/
│   ├── settings.json          # { "browser_profile_path": "...", "gmail_creds_path": "..." }
│   └── credentials.json
├── data/
│   ├── images/
│   └── history/               # 発送済みIDリストなどの履歴保存
└── logs/
```

### 2.1 `src/main.py`
**責任:** GUIの構築、イベントハンドリング、およびスレッド制御。

**スレッド設計:**
*   **メインスレッド:** Fletイベントループ（UIの描画・更新）
*   **ワーカースレッド:** 各業務処理（出品・発送・再出品）は `threading.Thread` で別スレッド実行
*   **通知方法:** ワーカースレッドからUIへの更新は `page.update()` を使用（Fletはスレッドセーフ）
*   **キュー:** `queue.Queue` を使用してログメッセージをメインスレッドへ送信

```python
# スレッド制御の概念コード
import threading
from queue import Queue

class WorkerThread(threading.Thread):
    def __init__(self, task_func, log_queue: Queue, on_complete):
        super().__init__(daemon=True)
        self.task_func = task_func
        self.log_queue = log_queue
        self.on_complete = on_complete

    def run(self):
        try:
            self.task_func(self.log_queue)
        finally:
            self.on_complete()
```

### 2.2 `src/config.py`
**責任:** 環境（開発時/exe実行時）を判定し、設定ファイルへの正しい絶対パスを提供する。

*   `get_base_path() -> Path`:
    *   `sys.frozen` (PyInstaller) かどうかで分岐し、`.exe` のあるディレクトリまたはソースディレクトリを特定して返す。
*   `load_settings()`: `get_base_path()` を基点に `config/settings.json` を読み込む。

### 2.3 `src/models/item.py`
**責任:** 出品商品データの定義。

```python
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
from enum import Enum

class ItemCondition(Enum):
    """商品状態"""
    NEW = "新品、未使用"
    LIKE_NEW = "未使用に近い"
    GOOD = "目立った傷や汚れなし"
    FAIR = "やや傷や汚れあり"
    POOR = "傷や汚れあり"
    BAD = "全体的に状態が悪い"

class ShippingMethod(Enum):
    """配送方法"""
    SAGAWA = "佐川急便"
    YAMATO = "ヤマト運輸"
    YUPACK = "ゆうパック"
    NEKOPOS = "ネコポス"

@dataclass
class ListingItem:
    """出品商品データモデル"""
    # 必須項目
    name: str                          # 商品名
    price: int                         # 開始価格（円）

    # 任意項目（デフォルト値あり）
    description: str = ""              # 商品説明
    category: str = ""                 # カテゴリ（ヤフオクカテゴリID or 名称）
    condition: ItemCondition = ItemCondition.GOOD  # 商品状態
    shipping_method: ShippingMethod = ShippingMethod.SAGAWA  # 配送方法
    shipping_cost: int = 0             # 送料（0=出品者負担）
    auction_duration: int = 7          # オークション期間（日）

    # 画像
    image_paths: List[Path] = field(default_factory=list)

    # メタ情報
    email_message_id: Optional[str] = None   # 元メールのID
    auction_id: Optional[str] = None         # 出品後に付与されるオークションID

    # 落札情報（発送時に使用）
    buyer_name: Optional[str] = None         # 購入者氏名
    buyer_address: Optional[str] = None      # 配送先住所
    buyer_phone: Optional[str] = None        # 電話番号
    buyer_postal_code: Optional[str] = None  # 郵便番号

@dataclass
class ShippingRecord:
    """発送履歴レコード"""
    auction_id: str
    shipped_at: str                    # ISO 8601形式
    tracking_number: Optional[str] = None
```

### 2.4 `src/services/browser_service.py`
**責任:** Playwrightのライフサイクル管理および、**競合プロセスの検知**。

**重要:** ユーザーの普段使用しているブラウザプロファイルを指定して起動する「**ステートフルモード**」で実装する。これにより、既存の認証情報（Cookie/Session）を流用し、2段階認証やCAPTCHAを回避する。

**タイムアウト・リトライ設定:**

| 項目 | デフォルト値 | 説明 |
| :--- | :--- | :--- |
| `DEFAULT_TIMEOUT_MS` | 30000 (30秒) | ページ読み込み・要素待機のタイムアウト |
| `NAVIGATION_TIMEOUT_MS` | 60000 (60秒) | ページ遷移のタイムアウト |
| `MAX_RETRY_COUNT` | 3 | ネットワークエラー時のリトライ回数 |
| `RETRY_DELAY_MS` | 2000 (2秒) | リトライ間隔 |

*   `check_chrome_conflict() -> bool`:
    *   `psutil` を使用し、ユーザー定義の Chrome プロファイルを使用しているプロセスが既に存在しないか確認する。
    *   起動中の場合、Falseを返し、GUI側で「Chromeを閉じてください」と警告を表示させるための判定を行う。

*   `launch_browser_context() -> BrowserContext`:
    *   Playwrightの `launch_persistent_context()` を使用してステートフルモードで起動。
    *   `headless=False` で起動し、ユーザーが操作状況を確認できるようにする。

*   `with_retry(func, max_retries: int = MAX_RETRY_COUNT) -> Any`:
    *   ネットワークエラーやタイムアウト発生時に指定回数リトライするラッパー関数。

```python
from playwright.sync_api import sync_playwright, BrowserContext, TimeoutError
import psutil
import time

# タイムアウト・リトライ設定
DEFAULT_TIMEOUT_MS = 30000
NAVIGATION_TIMEOUT_MS = 60000
MAX_RETRY_COUNT = 3
RETRY_DELAY_MS = 2000

def check_chrome_conflict(profile_path: str) -> bool:
    """Chromeが起動中かチェック（True=競合なし、False=競合あり）"""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if 'chrome' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if profile_path in cmdline:
                    return False  # 競合あり
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return True  # 競合なし

def launch_browser_context(profile_path: str) -> BrowserContext:
    """ステートフルモードでブラウザを起動"""
    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=profile_path,
        headless=False,
        args=["--start-maximized"],
        viewport=None,  # フルスクリーン対応
    )
    # デフォルトタイムアウトを設定
    context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    return context

def with_retry(func, max_retries: int = MAX_RETRY_COUNT):
    """リトライ付きで関数を実行"""
    for attempt in range(max_retries):
        try:
            return func()
        except TimeoutError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(RETRY_DELAY_MS / 1000)
```

### 2.5 `src/services/auction_service.py`
**責任:** ヤフオク!およびYahoo!ショッピングへの出品・再出品処理。

*   `list_new_item(context, item: ListingItem) -> bool`:
    *   新規出品処理を実行。取得したデータを各フィールドに入力し、画像をアップロード。
    *   **エラー処理:** データ不備などでエラーが発生した場合は、その商品のみエラーログに記録し、次の商品の処理へ進む（**スキップ＆継続**）。

*   `get_unsold_items(context) -> List[ListingItem]`:
    *   ヤフオク管理画面（マイオク > 出品終了分）で「落札者なしで終了」した商品リストを取得。

*   `relist_item(context, item: ListingItem) -> bool`:
    *   対象商品を再出品処理。
    *   **エラー処理:** 同様にスキップ＆継続。

*   `relist_all_unsold(context) -> Tuple[int, int]`:
    *   全ての未落札商品を順次再出品し、成功件数とスキップ件数を返す。

**ヤフオク出品時のデフォルト設定:**

| 項目 | デフォルト値 | 設定方法 |
| :--- | :--- | :--- |
| オークション期間 | 7日間 | メールで指定可能（【期間】タグ） |
| 商品状態 | 目立った傷や汚れなし | メールで指定可能（【状態】タグ） |
| 配送方法 | 佐川急便 | メールで指定可能（【配送】タグ） |
| 送料負担 | 出品者負担 | 固定 |
| 自動延長 | ON | 固定 |
| 早期終了 | ON | 固定 |
| 返品可否 | 返品不可 | 固定 |

### 2.6 `src/services/shipping_service.py`
**責任:** 「発送」業務フローの実行。**重複登録の防止処理**を含む。

*   `get_sold_items(context) -> List[ListingItem]`:
    *   ヤフオク管理画面（マイオク > 落札分 > 取引ナビ）から情報を取得。
    *   **対象:** 「支払い完了」かつ「未発送」ステータスの商品。
    *   取得後、**`utils.file_manager` の履歴照合機能**を呼び出す。
    *   既に処理済み（履歴IDリストにある）商品はリストから除外する。

*   `register_shipping(context, item) -> bool`:
    *   佐川急便「e飛伝Web」へアクセスし、送り状発行データを登録。
    *   登録成功後、**即座にそのオークションIDを履歴ファイルへ書き込む**。これにより、実行中にアプリが落ちても再開時の重複を防ぐ。
    *   **重要:** 住所不備やシステムエラー発生時は、例外を送出し、処理を中断する（スキップしない）。

### 2.7 `src/services/gmail_service.py`
**責任:** Gmail操作。**初回認証UXの考慮**および**処理済みメールの管理**。

*   `authenticate_gmail() -> Resource`:
    *   `token.json` が無く新規認証が必要な場合、コンソールで止まらないよう、`LocalServer` を用いたOAuthフローを実行する。
    *   GUI側(`main.py`)へ「認証待機中」ステータスを通知できる設計が望ましい（今回は同期呼び出しのため、実行前にダイアログを出す運用とする）。

*   `get_listing_emails() -> List[Message]`:
    *   Gmail APIを使用し、未処理の「出品依頼メール」を取得。
    *   **検索条件:** 件名に「出品依頼」を含み、ラベル「出品済み」が**付いていない**メール。

*   `mark_as_processed(message_id: str) -> bool`:
    *   処理完了したメールに「出品済み」ラベルを付与する。
    *   ラベルが存在しない場合は自動作成する。
    *   **呼び出しタイミング:** 出品成功後、またはエラースキップ後（再処理防止のため）

*   `download_attachments(message_id: str, save_dir: Path) -> List[Path]`:
    *   添付ファイル（商品画像）をダウンロードして保存。
    *   **ファイル名形式:** `{message_id}_{index:02d}.{ext}`（例: `abc123_01.jpg`）
    *   対応形式: JPEG, PNG, GIF, WebP

*   `send_reply(message_id, text) -> bool`:
    *   出品完了時、依頼メールに対して完了通知を返信する。
    *   **設定依存:** `settings.json` の `enable_reply_notification` が `true` の場合のみ実行。

**完了通知メールテンプレート:**

```text
件名: Re: 出品依頼

以下の商品の出品が完了しました。

商品名: {item_name}
オークションID: {auction_id}
出品URL: https://page.auctions.yahoo.co.jp/jp/auction/{auction_id}

---
本メールは自動送信されています。
```

### 2.8 `src/utils/file_manager.py`
**責任:** 一時ファイルおよび**ステータス管理ファイル**の操作。

*   `cleanup_item_images(item: ListingItem, force: bool = False)`:
    *   画像削除。
    *   `force=True` の場合、エラースキップ時でも削除（孤児画像防止）。

*   `cleanup_orphan_images(max_age_hours: int = 24)`:
    *   `data/images/` 内で作成から指定時間経過した画像を削除。
    *   アプリ起動時に自動実行（孤児画像の定期クリーンアップ）。

*   `load_shipped_history() -> Set[str]`: `data/history/shipped_ids.json` からIDセットを読み込む。

*   `save_shipped_id(auction_id: str, tracking_number: str = None)`: 指定IDを履歴ファイルに追記保存する。

*   `cleanup_old_history(days: int = 90)`:
    *   指定日数より古い発送履歴レコードを削除。
    *   アプリ起動時に自動実行（履歴ファイルの肥大化防止）。

**発送履歴ファイル仕様 (`data/history/shipped_ids.json`):**

| 項目 | 仕様 |
| :--- | :--- |
| 保存場所 | `data/history/` ディレクトリ |
| ファイル名 | `shipped_ids.json` |
| 保持期間 | 90日（古いレコードは自動削除） |
| 形式 | JSON |

```json
{
  "shipped_items": [
    {
      "auction_id": "abc123",
      "shipped_at": "2026-01-29T10:30:00+09:00",
      "tracking_number": "123456789012"
    },
    {
      "auction_id": "def456",
      "shipped_at": "2026-01-29T14:00:00+09:00",
      "tracking_number": null
    }
  ]
}
```

### 2.9 `src/utils/text_parser.py`
**責任:** 出品依頼メールの本文解析。

*   `parse_listing_email(body: str) -> dict`:
    *   メール本文内の定型タグを正規表現で抽出。
    *   戻り値: `{ "name": str, "price": int, "description": str, "category": str, ... }`

*   `validate_listing_data(data: dict) -> Tuple[bool, List[str]]`:
    *   必須項目（商品名、価格）の欠如をチェック。
    *   不備がある場合は `(False, ["商品名が未入力", ...])` を返す。

**メール解析タグ仕様（完全版）:**

| タグ名 | 必須 | 説明 | 例 |
| :--- | :--- | :--- | :--- |
| **【商品名】** | ✅ | 商品のタイトル（最大65文字） | `【商品名】UNIQLO ダウンジャケット 黒 Mサイズ` |
| **【価格】** | ✅ | 開始価格（数値のみ、円記号不要） | `【価格】3000` |
| **【説明】** | - | 商品の詳細説明 | `【説明】2回着用のみ。目立つ傷なし。` |
| **【カテゴリ】** | - | ヤフオクカテゴリ名 or ID | `【カテゴリ】メンズファッション > ジャケット` |
| **【状態】** | - | 商品状態（下記選択肢） | `【状態】目立った傷や汚れなし` |
| **【配送】** | - | 配送方法 | `【配送】佐川急便` |
| **【期間】** | - | オークション期間（1〜7日） | `【期間】5` |

**【状態】の選択肢:**
- 新品、未使用
- 未使用に近い
- 目立った傷や汚れなし（デフォルト）
- やや傷や汚れあり
- 傷や汚れあり
- 全体的に状態が悪い

**メール形式例:**

```text
件名: 出品依頼

【商品名】UNIQLO ダウンジャケット 黒 Mサイズ
【価格】3000
【説明】2回着用のみ。目立つ傷なし。裏地に小さなシミあり。
【状態】やや傷や汚れあり
【カテゴリ】メンズファッション > ジャケット
【期間】7

※ 添付画像: 商品写真1〜3枚
```

### 2.10 `src/utils/logger.py`
**責任:** ログ出力基盤。

**ログファイル仕様:**

| 項目 | 仕様 |
| :--- | :--- |
| 保存場所 | `logs/` ディレクトリ |
| ファイル名 | `app_YYYY-MM-DD.json` |
| ローテーション | 日次（1日1ファイル） |
| 保持期間 | 30日（古いログは自動削除） |
| 形式 | JSON Lines (1行1レコード) |

**ログレコード形式:**

```json
{
  "timestamp": "2026-01-29T10:00:00+09:00",
  "level": "INFO",
  "module": "auction_service",
  "message": "出品完了",
  "details": {
    "auction_id": "abc123",
    "item_name": "UNIQLO ダウンジャケット"
  }
}
```

**ログレベル:**
- `DEBUG`: 詳細なデバッグ情報
- `INFO`: 正常処理の記録
- `WARNING`: 警告（処理は継続）
- `ERROR`: エラー（処理中断またはスキップ）
- `CRITICAL`: 致命的エラー（アプリ停止）

---

## 3. データ詳細フロー & ライフサイクル

1.  **起動 & チェック**
    *   `config.py` ロード。
    *   `file_manager.cleanup_orphan_images()` で孤児画像を削除。
    *   `file_manager.cleanup_old_history()` で古い発送履歴を削除。
    *   `browser_service.check_chrome_conflict()` → 失敗ならアラート出して終了。

2.  **出品処理フロー**
    *   `gmail_service.get_listing_emails()` でメール取得。
    *   `text_parser.parse_listing_email()` で本文解析。
    *   `text_parser.validate_listing_data()` でバリデーション。
    *   `gmail_service.download_attachments()` で画像保存。
    *   `auction_service.list_new_item()` で出品実行。
    *   `gmail_service.mark_as_processed()` でメールに「出品済み」ラベル付与。
    *   `gmail_service.send_reply()` で完了通知（オプション）。
    *   `file_manager.cleanup_item_images()` で画像削除。

3.  **発送処理フロー**
    *   `shipping_service.get_sold_items()`
        *   -> `file_manager.load_shipped_history()` 読み込み。
        *   -> 履歴にあるIDはスキップ。
    *   `shipping_service.register_shipping()`
        *   -> e飛伝登録成功。
        *   -> `file_manager.save_shipped_id()` 追記。

4.  **再出品処理フロー**
    *   `auction_service.get_unsold_items()` で未落札商品取得。
    *   `auction_service.relist_all_unsold()` で一括再出品。

5.  **後始末**
    *   画像削除など。

---

## 4. エラーハンドリング運用規定

| 業務 | エラー処理方針 | 理由 |
| :--- | :--- | :--- |
| **出品業務** | スキップ＆継続 | 1件の不備で全体を止める必要はない |
| **発送業務** | 即時停止（アラート） | 誤配送防止のため確認が必要 |
| **再出品業務** | スキップ＆継続 | 1件の不備で全体を止める必要はない |

### 4.1 Chrome競合エラー
*   `main.py` で `check_chrome_conflict()` が引っかかった場合、赤色のダイアログで「Google Chromeが起動しています。終了してから再試行してください」と明確に表示し、処理を中断する。

### 4.2 出品業務のエラー（スキップ＆継続）
*   データ不備（必須項目欠如、画像なし等）が発生した場合:
    1.  エラーログに商品情報と理由を記録
    2.  該当商品をスキップし、次の商品の処理へ進む
    3.  処理完了後、スキップ件数をサマリ表示

### 4.3 発送業務のエラー（即時停止）
*   住所不備やシステム連携エラー時は、誤配送防止のため**処理を即時中断**し、ユーザーに確認を促すアラートを表示する。
*   1件でもエラーが発生したら、以降の処理を**即時停止（Break）**する（スキップして継続しない）。

### 4.4 再出品業務のエラー（スキップ＆継続）
*   再出品失敗時は、出品業務と同様にスキップして次へ進む。

---

## 5. 配布・実行環境（デプロイ設計）

### 5.1 依存ライブラリ

`requirements.txt` にて開発時点のバージョンを固定（Pinning）する。

```text
flet==0.21.2
playwright==1.41.0
google-api-python-client==2.111.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
psutil==5.9.7
```

### 5.2 Playwright初期設定

ユーザー環境での初回セットアップ時に以下を実行:

```bash
playwright install chromium
```

### 5.3 運用上の注意事項

*   ユーザーには「Chromeがインストールされていること」に加え、「**アプリ実行時はChromeを閉じること**」をマニュアル等で周知する。
*   Gmail API の `credentials.json` はユーザー自身がGoogle Cloud Consoleから取得する必要がある（セットアップマニュアル提供）。

---

## 6. UIデザイン仕様

### 6.1 メイン画面

```text
┌─────────────────────────────────────────────────────┐
│                  中古衣料品販売自動化システム           │
├─────────────────────────────────────────────────────┤
│                                                     │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│   │  ☀️ 朝      │  │  🌤️ 昼      │  │  🌙 夜      │ │
│   │             │  │             │  │             │ │
│   │   出 品     │  │   発 送     │  │   再出品    │ │
│   │             │  │             │  │             │ │
│   └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                     │
├─────────────────────────────────────────────────────┤
│ [ログ表示エリア]                                     │
│ [10:00] メール取得中: 5件...                         │
│ [10:01] 出品完了: 商品ID xxxxx                       │
│ [10:02] エラー: 商品ID yyyyy - 価格が未記入           │
│                                                     │
└─────────────────────────────────────────────────────┘
│ [⚙️ 設定]                                            │
└─────────────────────────────────────────────────────┘
```

*   **アクションボタン:** 中央に大きく3つ配置（出品 / 発送 / 再出品）
*   **推奨タイミング表示:** 各ボタンにアイコンとラベルで併記（朝・昼・夜）
*   **ログ表示エリア:** 画面下部にスクロール可能なテキストエリア
*   **リアルタイム更新:** 処理状況を即時表示（タイムスタンプ付き）

### 6.2 設定画面

| 項目 | 入力形式 | 説明 |
| :--- | :--- | :--- |
| Gmail認証情報パス | ファイル選択 | `credentials.json` のパス |
| ブラウザプロファイルパス | フォルダ選択 | Chrome プロファイルのパス |
| 完了通知返信 | ON/OFFトグル | 出品完了時にメール返信するか |

**設定値バリデーション:**

| 項目 | バリデーション内容 | エラー時の動作 |
| :--- | :--- | :--- |
| Gmail認証情報パス | ファイル存在確認、JSON形式検証、必須キー（`installed` or `web`）の存在確認 | 保存不可、エラーメッセージ表示 |
| ブラウザプロファイルパス | ディレクトリ存在確認 | 保存不可、エラーメッセージ表示 |

### 6.3 設定ファイル仕様 (`config/settings.json`)

**macOS の場合:**
```json
{
  "browser_profile_path": "/Users/xxx/Library/Application Support/Google/Chrome/Default",
  "gmail_creds_path": "./config/credentials.json",
  "enable_reply_notification": false
}
```

**Windows の場合:**
```json
{
  "browser_profile_path": "C:\\Users\\xxx\\AppData\\Local\\Google\\Chrome\\User Data\\Default",
  "gmail_creds_path": ".\\config\\credentials.json",
  "enable_reply_notification": false
}
```

---

## 7. 対応ECサイト一覧

| サイト | 対応業務 | 備考 |
| :--- | :--- | :--- |
| **ヤフオク!** | 出品、再出品、落札情報取得 | メイン対応 |
| **Yahoo!ショッピング** | 出品、再出品 | 将来対応予定（Phase 2以降） |
| **佐川急便 e飛伝Web** | 送り状発行、集荷依頼 | 発送業務用 |

※ Yahoo!ショッピングは初期リリースではスコープ外とし、基盤設計のみ考慮する。

---

## 8. 開発スケジュール・マイルストーン

### Phase 1: プロトタイプ作成 (Day 1-3)

| 日 | タスク | 成果物 |
| :--- | :--- | :--- |
| Day 1 | プロジェクト構成、Flet UIの基本実装 | `main.py`（3ボタン表示） |
| Day 2 | Gmail API接続確認、認証フロー実装 | `gmail_service.py` |
| Day 3 | Playwrightセットアップ、ブラウザ起動テスト | `browser_service.py` |

**Phase 1 完了条件:**
- 3つのボタンがUIに表示される
- Gmail認証が成功し、メール一覧が取得できる
- Chromeがステートフルモードで起動できる

### Phase 2: 各機能実装 (Day 4-10)

| 日 | タスク | 成果物 |
| :--- | :--- | :--- |
| Day 4-5 | 出品ロジック実装（メール解析、画像保存） | `text_parser.py`, `file_manager.py` |
| Day 6-7 | 出品ロジック実装（ヤフオク自動入力） | `auction_service.py` |
| Day 8 | 発送ロジック実装（落札情報取得） | `shipping_service.py` |
| Day 9 | 発送ロジック実装（e飛伝登録） | `shipping_service.py` |
| Day 10 | 再出品ロジック実装 | `auction_service.py` |

**Phase 2 完了条件:**
- 出品依頼メールから自動でヤフオクに出品できる
- 落札商品の情報をe飛伝に登録できる
- 未落札商品を一括再出品できる

### Phase 3: 結合テスト・運用調整 (Day 11-14)

| 日 | タスク | 成果物 |
| :--- | :--- | :--- |
| Day 11 | 結合テスト（実データ使用） | テスト結果レポート |
| Day 12 | エラーハンドリングの微調整 | 各サービスの例外処理改善 |
| Day 13 | PyInstallerによるパッケージング | `.exe` / `.app` ファイル |
| Day 14 | ドキュメント整備、デプロイ | ユーザーマニュアル |

**Phase 3 完了条件:**
- 実データで全フローが正常動作
- エラー発生時に適切にハンドリングされる
- 単体実行ファイルとして配布可能

---

## 10. テスト計画

### 10.1 テスト方針

| 項目 | 内容 |
| :--- | :--- |
| **テストフレームワーク** | pytest |
| **テストファイル配置** | `tests/` ディレクトリ |
| **命名規則** | `test_*.py`（ファイル）、`test_*`（関数） |
| **実行環境** | uv仮想環境（`uv run pytest`） |

### 10.2 テストレベルと対象

#### レベル1: ユニットテスト（単体テスト）

外部サービスに依存しない純粋なロジックのテスト。モックを活用。

| 対象モジュール | テスト内容 | 優先度 |
| :--- | :--- | :--- |
| `utils/text_parser.py` | メール本文解析、タグ抽出、バリデーション | 高 |
| `utils/file_manager.py` | 履歴ファイル読み書き、画像クリーンアップ | 高 |
| `utils/logger.py` | ログ出力、ファイルローテーション | 中 |
| `models/item.py` | データモデル生成、Enum変換 | 中 |
| `config.py` | パス解決、設定読み書き、バリデーション | 中 |

#### レベル2: 統合テスト（モック使用）

外部サービスをモックした状態での統合テスト。

| 対象モジュール | テスト内容 | モック対象 |
| :--- | :--- | :--- |
| `services/gmail_service.py` | 認証フロー、メール取得、ラベル操作 | Gmail API |
| `services/browser_service.py` | Chrome競合チェック、コンテキスト管理 | psutil, Playwright |
| `services/auction_service.py` | 出品・再出品フロー | Playwright Page |
| `services/shipping_service.py` | 発送登録、重複防止 | Playwright Page |

#### レベル3: E2Eテスト（結合テスト）

実際のブラウザを使用した結合テスト。**手動実行**または**ステージング環境**で実施。

| テストシナリオ | 前提条件 | 確認項目 |
| :--- | :--- | :--- |
| 出品フロー全体 | Gmail認証済み、テスト用メール準備 | メール取得→解析→出品→ラベル付与 |
| 発送フロー全体 | e飛伝ログイン済み、テスト用落札データ | 落札取得→登録→履歴保存 |
| 再出品フロー全体 | テスト用未落札商品 | 未落札取得→再出品→ID更新 |
| GUI操作 | アプリ起動 | ボタン操作、ログ表示、設定保存 |

### 10.3 テストケース詳細

#### `test_text_parser.py`

```python
# テストケース一覧
def test_parse_listing_email_full_tags():
    """全タグが含まれるメールの解析"""

def test_parse_listing_email_required_only():
    """必須タグのみのメール解析"""

def test_parse_listing_email_missing_required():
    """必須タグ欠損時のエラー処理"""

def test_parse_listing_email_invalid_price():
    """価格が不正な場合"""

def test_parse_listing_email_long_name():
    """商品名が65文字を超える場合の切り詰め"""

def test_validate_listing_data_valid():
    """有効なデータのバリデーション"""

def test_validate_listing_data_missing_name():
    """商品名欠損時のエラー"""

def test_validate_listing_data_invalid_duration():
    """オークション期間が範囲外の場合"""
```

#### `test_file_manager.py`

```python
def test_load_shipped_history_empty():
    """履歴ファイルが存在しない場合"""

def test_load_shipped_history_valid():
    """有効な履歴ファイルの読み込み"""

def test_save_shipped_id_new():
    """新規IDの保存"""

def test_save_shipped_id_append():
    """既存履歴への追記"""

def test_cleanup_old_history():
    """古い履歴の削除"""

def test_cleanup_orphan_images():
    """孤児画像の削除"""
```

#### `test_config.py`

```python
def test_get_base_path_development():
    """開発環境でのパス解決"""

def test_load_settings_default():
    """デフォルト設定の読み込み"""

def test_save_settings():
    """設定の保存"""

def test_validate_settings_valid():
    """有効な設定のバリデーション"""

def test_validate_settings_invalid_path():
    """無効なパスのバリデーション"""
```

#### `test_models.py`

```python
def test_listing_item_creation():
    """ListingItemの生成"""

def test_item_condition_from_string():
    """文字列からItemConditionへの変換"""

def test_shipping_record_to_dict():
    """ShippingRecordの辞書変換"""
```

### 10.4 テスト実行方法

```bash
# uv環境でのテスト実行

# 全テスト実行
uv run pytest

# 詳細出力で実行
uv run pytest -v

# 特定ファイルのみ
uv run pytest tests/test_text_parser.py

# 特定テスト関数のみ
uv run pytest tests/test_text_parser.py::test_parse_listing_email_full_tags

# カバレッジ計測
uv run pytest --cov=src --cov-report=html

# 最初の失敗で停止
uv run pytest -x --tb=short
```

### 10.5 テストデータ

#### テスト用メールサンプル (`tests/fixtures/sample_email.txt`)

```text
【商品名】UNIQLO ダウンジャケット 黒 Mサイズ
【価格】3000
【説明】2回着用のみ。目立つ傷なし。
【状態】やや傷や汚れあり
【カテゴリ】メンズファッション > ジャケット
【期間】7
```

#### テスト用発送履歴 (`tests/fixtures/shipped_ids.json`)

```json
{
  "shipped_items": [
    {
      "auction_id": "test123",
      "shipped_at": "2026-01-29T10:00:00+09:00",
      "tracking_number": "123456789012"
    }
  ]
}
```

### 10.6 CI/CD連携（将来対応）

| 項目 | 設定 |
| :--- | :--- |
| トリガー | プルリクエスト作成時、mainブランチへのプッシュ時 |
| 実行環境 | GitHub Actions（ubuntu-latest, Python 3.12） |
| 実行内容 | ユニットテスト、統合テスト（モック） |
| 除外 | E2Eテスト（手動実行のみ） |

### 10.7 品質基準

| 指標 | 目標値 |
| :--- | :--- |
| ユニットテストカバレッジ | 80%以上 |
| 統合テスト成功率 | 100% |
| E2Eテスト成功率 | 95%以上（ネットワーク起因の失敗を許容） |

---

## 11. 前提条件

*   クライアント側でGmail APIプロジェクトの作成と有効化が可能であること（サポート実施）。
*   佐川急便「e飛伝Web」のアカウントが利用可能であること。
*   実行PCにGoogle Chromeがインストールされていること。
*   アプリ実行時はGoogle Chromeを終了していること。
