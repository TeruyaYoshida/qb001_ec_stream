"""
ブラウザ起動管理・プロセスチェックモジュール
Playwrightのライフサイクル管理および、競合プロセスの検知を行う。
ステートフルモード（既存Chromeプロファイル利用）で実装。
"""

import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

import psutil
from playwright.sync_api import (
    sync_playwright,
    BrowserContext,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from config import get_browser_profile_path

# タイムアウト・リトライ設定
DEFAULT_TIMEOUT_MS = 30000      # 要素待機タイムアウト（30秒）
NAVIGATION_TIMEOUT_MS = 60000   # ページ遷移タイムアウト（60秒）
MAX_RETRY_COUNT = 3             # ネットワークエラー時のリトライ回数
RETRY_DELAY_MS = 2000           # リトライ間隔（2秒）

# ブラウザ起動引数
# 自動処理用（出品/発送/再出品）
BROWSER_ARGS_AUTOMATION = [
    "--start-maximized",
    "--disable-extensions",           # 拡張機能を無効化（安定性向上）
    "--disable-background-timer-throttling",  # バックグラウンド処理の制限を解除
    "--disable-backgrounding-occluded-windows",
    "--no-first-run",                 # 初回起動ウィザードをスキップ
    "--no-default-browser-check",     # デフォルトブラウザ確認をスキップ
    "--disable-blink-features=AutomationControlled", # 自動操作検知の回避
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 認証設定用（パスワードマネージャー等を使用可能に）
BROWSER_ARGS_AUTH = [
    "--start-maximized",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-blink-features=AutomationControlled",  # 自動操作検知の回避
    "--disable-infobars",  # 「Chromeは自動テストソフトウェアによって制御されています」バーを非表示
]

# グローバル変数でPlaywrightインスタンスを保持
_playwright_instance: Optional[Playwright] = None
_browser_context: Optional[BrowserContext] = None





def launch_browser_context() -> BrowserContext:
    """
    専用プロファイルでブラウザを起動する。
    プロファイルディレクトリが存在しない場合は自動作成する。

    Returns:
        BrowserContextインスタンス

    Raises:
        Exception: ブラウザ起動に失敗した場合
    """
    global _playwright_instance, _browser_context

    profile_path = get_browser_profile_path()
    profile_path.mkdir(parents=True, exist_ok=True)

    # 既存のコンテキストがあれば閉じる
    if _browser_context:
        try:
            _browser_context.close()
        except Exception:
            pass

    # Playwrightインスタンスを作成
    _playwright_instance = sync_playwright().start()

    # 専用プロファイルでブラウザを起動
    _browser_context = _playwright_instance.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        headless=False,
        args=BROWSER_ARGS_AUTOMATION,
        viewport=None,
    )

    # 自動操作フラグを隠蔽するスクリプトを注入
    _browser_context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    # デフォルトタイムアウトを設定
    _browser_context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    _browser_context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)

    return _browser_context





def launch_auth_browser() -> None:
    """
    認証設定用に通常のChromeブラウザを起動する。
    専用プロファイルディレクトリを使用し、3つのログインページを開く。
    ユーザーがブラウザを閉じるまで待機する。
    """
    import subprocess
    import shutil
    
    profile_path = get_browser_profile_path()
    profile_path.mkdir(parents=True, exist_ok=True)

    # macOS用Chromeのパス
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    
    chrome_path = None
    for path in chrome_paths:
        if Path(path).exists():
            chrome_path = path
            break
    
    if not chrome_path:
        raise Exception(
            "Google Chromeが見つかりません。\n"
            "/Applications/Google Chrome.app にインストールしてください。"
        )

    # 開くURL一覧
    urls = [
        "https://login.yahoo.co.jp/",
        "https://www.e-service.sagawa-exp.co.jp/",
        "https://accounts.google.com/",
    ]

    # Chromeを専用プロファイルで起動
    cmd = [
        chrome_path,
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
    ] + urls

    print(f"Chromeを起動しています...")
    print(f"プロファイル: {profile_path}")
    
    # Chromeを起動し、終了するまで待機
    process = subprocess.Popen(cmd)
    process.wait()  # ユーザーがブラウザを閉じるまで待機


def close_browser_context() -> None:
    """
    ブラウザコンテキストを閉じる。
    """
    global _playwright_instance, _browser_context

    if _browser_context:
        try:
            _browser_context.close()
        except Exception:
            pass
        _browser_context = None

    if _playwright_instance:
        try:
            _playwright_instance.stop()
        except Exception:
            pass
        _playwright_instance = None


def with_retry(
    func: Callable[[], Any],
    max_retries: int = MAX_RETRY_COUNT,
    delay_ms: int = RETRY_DELAY_MS,
    retry_exceptions: tuple = (PlaywrightTimeoutError, ConnectionError),
) -> Any:
    """
    リトライ付きで関数を実行する。

    ネットワークエラーやタイムアウト発生時に指定回数リトライする。

    Args:
        func: 実行する関数
        max_retries: 最大リトライ回数
        delay_ms: リトライ間隔（ミリ秒）
        retry_exceptions: リトライ対象の例外タプル

    Returns:
        関数の戻り値

    Raises:
        Exception: 最大リトライ回数を超えた場合、最後の例外を再送出
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except retry_exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(delay_ms / 1000)

    # 最大リトライ回数を超えた場合
    raise last_exception


def get_current_context() -> Optional[BrowserContext]:
    """
    現在のブラウザコンテキストを取得する。

    Returns:
        BrowserContextインスタンス、または未起動の場合None
    """
    return _browser_context
