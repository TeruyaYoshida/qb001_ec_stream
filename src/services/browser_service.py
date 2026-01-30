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

# タイムアウト・リトライ設定
DEFAULT_TIMEOUT_MS = 30000      # 要素待機タイムアウト（30秒）
NAVIGATION_TIMEOUT_MS = 60000   # ページ遷移タイムアウト（60秒）
MAX_RETRY_COUNT = 3             # ネットワークエラー時のリトライ回数
RETRY_DELAY_MS = 2000           # リトライ間隔（2秒）

# グローバル変数でPlaywrightインスタンスを保持
_playwright_instance: Optional[Playwright] = None
_browser_context: Optional[BrowserContext] = None


def check_chrome_conflict(profile_path: str) -> Tuple[bool, str]:
    """
    Chromeが起動中かチェックする。
    
    指定されたプロファイルパスを使用しているChromeプロセスが
    既に存在しないか確認する。
    
    Args:
        profile_path: Chromeプロファイルのパス
        
    Returns:
        (競合なしの場合True、メッセージ)
    """
    if not profile_path:
        return False, "ブラウザプロファイルパスが設定されていません"
    
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            proc_name = proc.info.get('name', '')
            if proc_name and 'chrome' in proc_name.lower():
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline)
                if profile_path in cmdline_str:
                    return False, "Google Chromeが起動しています。終了してから再試行してください。"
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # プロセス情報取得エラーは無視
            continue
    
    return True, "競合なし"


def launch_browser_context(profile_path: str) -> BrowserContext:
    """
    ステートフルモードでブラウザを起動する。
    
    ユーザーの普段使用しているブラウザプロファイルを指定して起動し、
    既存の認証情報（Cookie/Session）を流用する。
    
    Args:
        profile_path: Chromeプロファイルのパス
        
    Returns:
        BrowserContextインスタンス
        
    Raises:
        Exception: ブラウザ起動に失敗した場合
    """
    global _playwright_instance, _browser_context
    
    if not profile_path:
        raise ValueError("ブラウザプロファイルパスが設定されていません")
    
    # 既存のコンテキストがあれば閉じる
    if _browser_context:
        try:
            _browser_context.close()
        except Exception:
            pass
    
    # Playwrightインスタンスを作成
    _playwright_instance = sync_playwright().start()
    
    # ステートフルモードでブラウザを起動
    _browser_context = _playwright_instance.chromium.launch_persistent_context(
        user_data_dir=profile_path,
        headless=False,  # デバッグとCAPTCHA対応のため表示モード
        args=["--start-maximized"],
        viewport=None,  # フルスクリーン対応
    )
    
    # デフォルトタイムアウトを設定
    _browser_context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    _browser_context.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    
    return _browser_context


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
