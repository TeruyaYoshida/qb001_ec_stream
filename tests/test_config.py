"""
config モジュールのユニットテスト
"""

import json
from pathlib import Path

import pytest

from config import (
    get_base_path,
    get_config_path,
    get_data_path,
    get_logs_path,
    load_settings,
    save_settings,
    validate_settings,
    ensure_directories,
)


class TestPathFunctions:
    """パス関連関数のテスト"""

    def test_get_base_path(self):
        """ベースパスの取得"""
        base_path = get_base_path()

        assert base_path.exists()
        assert base_path.is_dir()

    def test_get_config_path(self):
        """設定パスの取得"""
        config_path = get_config_path()

        assert "config" in str(config_path)

    def test_get_data_path(self):
        """データパスの取得"""
        data_path = get_data_path()

        assert "data" in str(data_path)

    def test_get_logs_path(self):
        """ログパスの取得"""
        logs_path = get_logs_path()

        assert "logs" in str(logs_path)


class TestLoadSettings:
    """load_settings関数のテスト"""

    def test_load_default_settings(self, tmp_path, monkeypatch):
        """デフォルト設定の読み込み（ファイルが存在しない場合）"""
        def mock_get_config_path():
            return tmp_path

        monkeypatch.setattr("config.get_config_path", mock_get_config_path)

        settings = load_settings()

        assert "browser_profile_path" in settings
        assert "gmail_creds_path" in settings
        assert "enable_reply_notification" in settings
        assert settings["enable_reply_notification"] is False

    def test_load_existing_settings(self, tmp_path, monkeypatch):
        """既存設定ファイルの読み込み"""
        # テスト用設定ファイルを作成
        settings_file = tmp_path / "settings.json"
        test_settings = {
            "browser_profile_path": "/test/path",
            "gmail_creds_path": "/test/creds.json",
            "enable_reply_notification": True,
        }
        settings_file.write_text(json.dumps(test_settings))

        def mock_get_config_path():
            return tmp_path

        monkeypatch.setattr("config.get_config_path", mock_get_config_path)

        settings = load_settings()

        assert settings["browser_profile_path"] == "/test/path"
        assert settings["enable_reply_notification"] is True


class TestSaveSettings:
    """save_settings関数のテスト"""

    def test_save_settings(self, tmp_path, monkeypatch):
        """設定の保存"""
        def mock_get_config_path():
            return tmp_path

        monkeypatch.setattr("config.get_config_path", mock_get_config_path)

        settings = {
            "browser_profile_path": "/test/path",
            "gmail_creds_path": "/test/creds.json",
            "enable_reply_notification": True,
        }

        result = save_settings(settings)

        assert result is True

        # 保存されたファイルを確認
        settings_file = tmp_path / "settings.json"
        assert settings_file.exists()

        saved_data = json.loads(settings_file.read_text())
        assert saved_data["browser_profile_path"] == "/test/path"


class TestValidateSettings:
    """validate_settings関数のテスト"""

    def test_validate_empty_paths(self):
        """空のパスは有効（未設定として許可）"""
        settings = {
            "browser_profile_path": "",
            "gmail_creds_path": "",
        }

        is_valid, errors = validate_settings(settings)

        # 空のパスはエラーにならない
        assert is_valid is True

    def test_validate_invalid_browser_path(self, tmp_path):
        """存在しないブラウザパス"""
        settings = {
            "browser_profile_path": "/nonexistent/path",
            "gmail_creds_path": "",
        }

        is_valid, errors = validate_settings(settings)

        assert is_valid is False
        assert any("ブラウザプロファイルパス" in e for e in errors)

    def test_validate_valid_browser_path(self, tmp_path):
        """有効なブラウザパス"""
        browser_dir = tmp_path / "chrome_profile"
        browser_dir.mkdir()

        settings = {
            "browser_profile_path": str(browser_dir),
            "gmail_creds_path": "",
        }

        is_valid, errors = validate_settings(settings)

        assert is_valid is True

    def test_validate_invalid_gmail_creds(self, tmp_path):
        """存在しないGmail認証情報ファイル"""
        settings = {
            "browser_profile_path": "",
            "gmail_creds_path": "/nonexistent/credentials.json",
        }

        is_valid, errors = validate_settings(settings)

        assert is_valid is False
        assert any("Gmail認証情報" in e for e in errors)

    def test_validate_invalid_gmail_creds_format(self, tmp_path):
        """無効なJSON形式のGmail認証情報"""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("invalid json")

        settings = {
            "browser_profile_path": "",
            "gmail_creds_path": str(creds_file),
        }

        is_valid, errors = validate_settings(settings)

        assert is_valid is False
        assert any("有効なJSON" in e for e in errors)

    def test_validate_gmail_creds_missing_keys(self, tmp_path):
        """必須キーがないGmail認証情報"""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"other_key": "value"}))

        settings = {
            "browser_profile_path": "",
            "gmail_creds_path": str(creds_file),
        }

        is_valid, errors = validate_settings(settings)

        assert is_valid is False
        assert any("必須キー" in e for e in errors)

    def test_validate_valid_gmail_creds(self, tmp_path):
        """有効なGmail認証情報"""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"installed": {"client_id": "test"}}))

        settings = {
            "browser_profile_path": "",
            "gmail_creds_path": str(creds_file),
        }

        is_valid, errors = validate_settings(settings)

        assert is_valid is True


class TestEnsureDirectories:
    """ensure_directories関数のテスト"""

    def test_ensure_directories(self, tmp_path, monkeypatch):
        """必要なディレクトリの作成"""
        def mock_get_base_path():
            return tmp_path

        monkeypatch.setattr("config.get_base_path", mock_get_base_path)

        # 既存の関数を新しいベースパスでオーバーライド
        def mock_get_config_path():
            return tmp_path / "config"

        def mock_get_data_path():
            return tmp_path / "data"

        def mock_get_logs_path():
            return tmp_path / "logs"

        def mock_get_images_path():
            return tmp_path / "data" / "images"

        def mock_get_history_path():
            return tmp_path / "data" / "history"

        monkeypatch.setattr("config.get_config_path", mock_get_config_path)
        monkeypatch.setattr("config.get_data_path", mock_get_data_path)
        monkeypatch.setattr("config.get_logs_path", mock_get_logs_path)
        monkeypatch.setattr("config.get_images_path", mock_get_images_path)
        monkeypatch.setattr("config.get_history_path", mock_get_history_path)

        ensure_directories()

        assert mock_get_config_path().exists()
        assert mock_get_data_path().exists()
        assert mock_get_logs_path().exists()
