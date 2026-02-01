"""
設定・パス解決モジュール
環境（開発時/exe実行時）を判定し、設定ファイルへの正しい絶対パスを提供する。
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def get_base_path() -> Path:
    """
    アプリケーションのベースパスを取得する。
    PyInstallerでビルドされた場合は.exeのあるディレクトリ、
    それ以外はソースディレクトリを返す。
    """
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた実行ファイルの場合
        return Path(sys.executable).parent
    else:
        # 開発環境の場合（srcディレクトリの親を返す）
        return Path(__file__).parent.parent


def get_config_path() -> Path:
    """設定ディレクトリのパスを取得"""
    return get_base_path() / "config"


def get_data_path() -> Path:
    """データディレクトリのパスを取得"""
    return get_base_path() / "data"


def get_logs_path() -> Path:
    """ログディレクトリのパスを取得"""
    return get_base_path() / "logs"


def get_images_path() -> Path:
    """画像ディレクトリのパスを取得"""
    return get_data_path() / "images"


def get_history_path() -> Path:
    """履歴ディレクトリのパスを取得"""
    return get_data_path() / "history"


def get_browser_profile_path() -> Path:
    """システム専用Chromeプロファイルのパスを取得"""
    return get_data_path() / "chrome_profile"


def load_settings() -> Dict[str, Any]:
    """
    設定ファイルを読み込む。
    ファイルが存在しない場合はデフォルト設定を返す。
    """
    settings_path = get_config_path() / "settings.json"

    default_settings = {
        "gmail_creds_path": str(get_config_path() / "credentials.json"),
        "enable_reply_notification": False
    }

    if not settings_path.exists():
        return default_settings

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            loaded_settings = json.load(f)
            # デフォルト値とマージ（ファイルにない項目はデフォルト値を使用）
            return {**default_settings, **loaded_settings}
    except (json.JSONDecodeError, IOError):
        return default_settings


def save_settings(settings: Dict[str, Any]) -> bool:
    """
    設定ファイルを保存する。

    Args:
        settings: 保存する設定辞書

    Returns:
        成功時True、失敗時False
    """
    settings_path = get_config_path() / "settings.json"

    try:
        # 設定ディレクトリが存在しない場合は作成
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def validate_settings(settings: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    設定値のバリデーションを行う。

    Args:
        settings: 検証する設定辞書

    Returns:
        (有効かどうか, エラーメッセージのリスト)
    """
    errors = []

    # Gmail認証情報パスの検証
    gmail_path = settings.get("gmail_creds_path", "")
    if gmail_path:
        gmail_path_obj = Path(gmail_path)
        if not gmail_path_obj.exists():
            errors.append(f"Gmail認証情報ファイルが存在しません: {gmail_path}")
        elif gmail_path_obj.exists():
            # JSON形式と必須キーの検証
            try:
                with open(gmail_path_obj, 'r', encoding='utf-8') as f:
                    creds_data = json.load(f)
                    if "installed" not in creds_data and "web" not in creds_data:
                        errors.append("Gmail認証情報ファイルに必須キー(installed/web)がありません")
            except json.JSONDecodeError:
                errors.append("Gmail認証情報ファイルが有効なJSONではありません")
            except IOError as e:
                errors.append(f"Gmail認証情報ファイルの読み込みエラー: {e}")

    return len(errors) == 0, errors


def ensure_directories() -> None:
    """
    必要なディレクトリを確認し、存在しない場合は作成する。
    アプリケーション起動時に呼び出される。
    """
    directories = [
        get_config_path(),
        get_data_path(),
        get_images_path(),
        get_history_path(),
        get_logs_path(),
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
