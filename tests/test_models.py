"""
models モジュールのユニットテスト
"""

from pathlib import Path

import pytest

from models.item import (
    ListingItem,
    ShippingRecord,
    ItemCondition,
    ShippingMethod,
)


class TestItemCondition:
    """ItemCondition Enumのテスト"""

    def test_from_string_valid(self):
        """有効な文字列からの変換"""
        assert ItemCondition.from_string("新品、未使用") == ItemCondition.NEW
        assert ItemCondition.from_string("目立った傷や汚れなし") == ItemCondition.GOOD
        assert ItemCondition.from_string("やや傷や汚れあり") == ItemCondition.FAIR

    def test_from_string_invalid(self):
        """無効な文字列からの変換（デフォルト値）"""
        assert ItemCondition.from_string("無効な状態") == ItemCondition.GOOD
        assert ItemCondition.from_string("") == ItemCondition.GOOD

    def test_value(self):
        """Enumの値を取得"""
        assert ItemCondition.NEW.value == "新品、未使用"
        assert ItemCondition.GOOD.value == "目立った傷や汚れなし"


class TestShippingMethod:
    """ShippingMethod Enumのテスト"""

    def test_from_string_valid(self):
        """有効な文字列からの変換"""
        assert ShippingMethod.from_string("佐川急便") == ShippingMethod.SAGAWA
        assert ShippingMethod.from_string("ヤマト運輸") == ShippingMethod.YAMATO
        assert ShippingMethod.from_string("ゆうパック") == ShippingMethod.YUPACK

    def test_from_string_invalid(self):
        """無効な文字列からの変換（デフォルト値）"""
        assert ShippingMethod.from_string("無効な配送方法") == ShippingMethod.SAGAWA
        assert ShippingMethod.from_string("") == ShippingMethod.SAGAWA


class TestListingItem:
    """ListingItemデータモデルのテスト"""

    def test_creation_minimal(self):
        """必須項目のみでの作成"""
        item = ListingItem(name="テスト商品", price=1000)

        assert item.name == "テスト商品"
        assert item.price == 1000
        assert item.description == ""
        assert item.condition == ItemCondition.GOOD
        assert item.shipping_method == ShippingMethod.SAGAWA
        assert item.auction_duration == 7
        assert item.image_paths == []

    def test_creation_full(self):
        """全項目を指定して作成"""
        item = ListingItem(
            name="テスト商品",
            price=2000,
            description="テスト説明",
            category="テストカテゴリ",
            condition=ItemCondition.NEW,
            shipping_method=ShippingMethod.YAMATO,
            auction_duration=5,
            image_paths=[Path("/tmp/test.jpg")],
            email_message_id="msg123",
            auction_id="auction456",
            buyer_name="テスト購入者",
            buyer_address="東京都渋谷区",
            buyer_phone="03-1234-5678",
            buyer_postal_code="150-0001",
        )

        assert item.name == "テスト商品"
        assert item.price == 2000
        assert item.description == "テスト説明"
        assert item.condition == ItemCondition.NEW
        assert item.shipping_method == ShippingMethod.YAMATO
        assert item.auction_duration == 5
        assert len(item.image_paths) == 1
        assert item.buyer_name == "テスト購入者"


class TestShippingRecord:
    """ShippingRecordデータモデルのテスト"""

    def test_creation(self):
        """ShippingRecordの作成"""
        record = ShippingRecord(
            auction_id="auction123",
            shipped_at="2026-01-29T10:00:00+09:00",
            tracking_number="tracking456",
        )

        assert record.auction_id == "auction123"
        assert record.shipped_at == "2026-01-29T10:00:00+09:00"
        assert record.tracking_number == "tracking456"

    def test_to_dict(self):
        """辞書形式への変換"""
        record = ShippingRecord(
            auction_id="auction123",
            shipped_at="2026-01-29T10:00:00+09:00",
            tracking_number="tracking456",
        )

        result = record.to_dict()

        assert result == {
            "auction_id": "auction123",
            "shipped_at": "2026-01-29T10:00:00+09:00",
            "tracking_number": "tracking456",
        }

    def test_from_dict(self):
        """辞書からの生成"""
        data = {
            "auction_id": "auction123",
            "shipped_at": "2026-01-29T10:00:00+09:00",
            "tracking_number": "tracking456",
        }

        record = ShippingRecord.from_dict(data)

        assert record.auction_id == "auction123"
        assert record.shipped_at == "2026-01-29T10:00:00+09:00"
        assert record.tracking_number == "tracking456"

    def test_from_dict_without_tracking(self):
        """追跡番号なしの辞書からの生成"""
        data = {
            "auction_id": "auction123",
            "shipped_at": "2026-01-29T10:00:00+09:00",
        }

        record = ShippingRecord.from_dict(data)

        assert record.auction_id == "auction123"
        assert record.tracking_number is None
