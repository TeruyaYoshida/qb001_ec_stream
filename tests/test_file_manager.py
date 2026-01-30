"""
file_manager モジュールのユニットテスト
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from utils.file_manager import (
    cleanup_item_images,
    cleanup_orphan_images,
    load_shipped_history,
    save_shipped_id,
    cleanup_old_history,
    _get_shipped_history_path,
)


class TestCleanupItemImages:
    """cleanup_item_images関数のテスト"""

    def test_cleanup_existing_images(self, tmp_path):
        """存在する画像の削除"""
        # テスト用画像ファイルを作成
        image1 = tmp_path / "test1.jpg"
        image2 = tmp_path / "test2.png"
        image1.write_text("dummy")
        image2.write_text("dummy")

        deleted_count = cleanup_item_images([image1, image2])

        assert deleted_count == 2
        assert not image1.exists()
        assert not image2.exists()

    def test_cleanup_nonexistent_images(self, tmp_path):
        """存在しない画像の削除（エラーにならない）"""
        nonexistent = tmp_path / "nonexistent.jpg"

        deleted_count = cleanup_item_images([nonexistent])

        assert deleted_count == 0

    def test_cleanup_mixed_images(self, tmp_path):
        """存在する画像と存在しない画像の混合"""
        existing = tmp_path / "existing.jpg"
        existing.write_text("dummy")
        nonexistent = tmp_path / "nonexistent.jpg"

        deleted_count = cleanup_item_images([existing, nonexistent])

        assert deleted_count == 1
        assert not existing.exists()


class TestShippedHistory:
    """発送履歴関連のテスト"""

    def test_load_shipped_history_empty(self, tmp_path, monkeypatch):
        """履歴ファイルが存在しない場合"""
        # 存在しないパスを返すようにモック
        def mock_get_history_path():
            return tmp_path / "history"

        monkeypatch.setattr(
            "utils.file_manager.get_history_path",
            mock_get_history_path
        )

        result = load_shipped_history()

        assert result == set()

    def test_load_shipped_history_valid(self, tmp_path, monkeypatch):
        """有効な履歴ファイルの読み込み"""
        # テスト用履歴ファイルを作成
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        history_file = history_dir / "shipped_ids.json"
        history_data = {
            "shipped_items": [
                {"auction_id": "abc123", "shipped_at": "2026-01-29T10:00:00+09:00"},
                {"auction_id": "def456", "shipped_at": "2026-01-29T11:00:00+09:00"},
            ]
        }
        history_file.write_text(json.dumps(history_data))

        def mock_get_history_path():
            return history_dir

        monkeypatch.setattr(
            "utils.file_manager.get_history_path",
            mock_get_history_path
        )

        result = load_shipped_history()

        assert result == {"abc123", "def456"}

    def test_save_shipped_id_new(self, tmp_path, monkeypatch):
        """新規IDの保存"""
        history_dir = tmp_path / "history"
        history_dir.mkdir()

        def mock_get_history_path():
            return history_dir

        monkeypatch.setattr(
            "utils.file_manager.get_history_path",
            mock_get_history_path
        )

        result = save_shipped_id("test123", "tracking456")

        assert result is True

        # ファイルの内容を確認
        history_file = history_dir / "shipped_ids.json"
        assert history_file.exists()

        data = json.loads(history_file.read_text())
        assert len(data["shipped_items"]) == 1
        assert data["shipped_items"][0]["auction_id"] == "test123"
        assert data["shipped_items"][0]["tracking_number"] == "tracking456"

    def test_save_shipped_id_append(self, tmp_path, monkeypatch):
        """既存履歴への追記"""
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        history_file = history_dir / "shipped_ids.json"

        # 既存データを作成
        existing_data = {
            "shipped_items": [
                {"auction_id": "existing123", "shipped_at": "2026-01-29T10:00:00+09:00"}
            ]
        }
        history_file.write_text(json.dumps(existing_data))

        def mock_get_history_path():
            return history_dir

        monkeypatch.setattr(
            "utils.file_manager.get_history_path",
            mock_get_history_path
        )

        result = save_shipped_id("new456")

        assert result is True

        # ファイルの内容を確認
        data = json.loads(history_file.read_text())
        assert len(data["shipped_items"]) == 2
        auction_ids = [item["auction_id"] for item in data["shipped_items"]]
        assert "existing123" in auction_ids
        assert "new456" in auction_ids


class TestCleanupOldHistory:
    """cleanup_old_history関数のテスト"""

    def test_cleanup_old_records(self, tmp_path, monkeypatch):
        """古い履歴の削除"""
        history_dir = tmp_path / "history"
        history_dir.mkdir()
        history_file = history_dir / "shipped_ids.json"

        # 古いレコードと新しいレコードを作成
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%S+09:00")
        new_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

        data = {
            "shipped_items": [
                {"auction_id": "old123", "shipped_at": old_date},
                {"auction_id": "new456", "shipped_at": new_date},
            ]
        }
        history_file.write_text(json.dumps(data))

        def mock_get_history_path():
            return history_dir

        monkeypatch.setattr(
            "utils.file_manager.get_history_path",
            mock_get_history_path
        )

        deleted_count = cleanup_old_history(days=90)

        assert deleted_count == 1

        # 新しいレコードのみ残っていることを確認
        updated_data = json.loads(history_file.read_text())
        assert len(updated_data["shipped_items"]) == 1
        assert updated_data["shipped_items"][0]["auction_id"] == "new456"
