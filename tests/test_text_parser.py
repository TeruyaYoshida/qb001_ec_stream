"""
text_parser モジュールのユニットテスト
"""

import pytest

from utils.text_parser import parse_listing_email, validate_listing_data


class TestParseListingEmail:
    """parse_listing_email関数のテスト"""

    def test_parse_full_tags(self):
        """全タグが含まれるメールの解析"""
        body = """
【商品名】UNIQLO ダウンジャケット 黒 Mサイズ
【価格】3000
【説明】2回着用のみ。目立つ傷なし。裏地に小さなシミあり。
【状態】やや傷や汚れあり
【カテゴリ】メンズファッション > ジャケット
【配送】佐川急便
【期間】7
"""
        result = parse_listing_email(body)

        assert result["name"] == "UNIQLO ダウンジャケット 黒 Mサイズ"
        assert result["price"] == 3000
        assert "2回着用のみ" in result["description"]
        assert result["condition"] == "やや傷や汚れあり"
        assert result["category"] == "メンズファッション > ジャケット"
        assert result["shipping_method"] == "佐川急便"
        assert result["auction_duration"] == 7

    def test_parse_required_only(self):
        """必須タグのみのメール解析"""
        body = """
【商品名】テスト商品
【価格】1000
"""
        result = parse_listing_email(body)

        assert result["name"] == "テスト商品"
        assert result["price"] == 1000
        # デフォルト値の確認
        assert result["condition"] == "目立った傷や汚れなし"
        assert result["shipping_method"] == "佐川急便"
        assert result["auction_duration"] == 7

    def test_parse_missing_required(self):
        """必須タグ欠損時"""
        body = """
【説明】商品説明のみ
"""
        result = parse_listing_email(body)

        assert result["name"] is None
        assert result["price"] is None

    def test_parse_invalid_price(self):
        """価格が不正な場合"""
        body = """
【商品名】テスト商品
【価格】abc
"""
        result = parse_listing_email(body)

        assert result["name"] == "テスト商品"
        assert result["price"] is None

    def test_parse_long_name(self):
        """商品名が65文字を超える場合の切り詰め"""
        long_name = "あ" * 100
        body = f"""
【商品名】{long_name}
【価格】1000
"""
        result = parse_listing_email(body)

        assert len(result["name"]) == 65

    def test_parse_invalid_condition(self):
        """無効な商品状態の場合はデフォルト値を使用"""
        body = """
【商品名】テスト商品
【価格】1000
【状態】無効な状態
"""
        result = parse_listing_email(body)

        assert result["condition"] == "目立った傷や汚れなし"

    def test_parse_invalid_duration(self):
        """オークション期間が範囲外の場合はデフォルト値を使用"""
        body = """
【商品名】テスト商品
【価格】1000
【期間】10
"""
        result = parse_listing_email(body)

        # 範囲外なのでデフォルト値のまま
        assert result["auction_duration"] == 7

    def test_parse_valid_duration_range(self):
        """オークション期間が有効範囲内の場合"""
        body = """
【商品名】テスト商品
【価格】1000
【期間】3
"""
        result = parse_listing_email(body)

        assert result["auction_duration"] == 3


class TestValidateListingData:
    """validate_listing_data関数のテスト"""

    def test_validate_valid_data(self):
        """有効なデータのバリデーション"""
        data = {
            "name": "テスト商品",
            "price": 1000,
            "auction_duration": 7,
        }
        is_valid, errors = validate_listing_data(data)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_name(self):
        """商品名欠損時のエラー"""
        data = {
            "name": None,
            "price": 1000,
        }
        is_valid, errors = validate_listing_data(data)

        assert is_valid is False
        assert "商品名が未入力です" in errors

    def test_validate_missing_price(self):
        """価格欠損時のエラー"""
        data = {
            "name": "テスト商品",
            "price": None,
        }
        is_valid, errors = validate_listing_data(data)

        assert is_valid is False
        assert "価格が未入力です" in errors

    def test_validate_invalid_price(self):
        """価格が不正な場合"""
        data = {
            "name": "テスト商品",
            "price": -100,
        }
        is_valid, errors = validate_listing_data(data)

        assert is_valid is False
        assert "価格は正の整数で入力してください" in errors

    def test_validate_long_name(self):
        """商品名が65文字を超える場合"""
        data = {
            "name": "あ" * 66,
            "price": 1000,
        }
        is_valid, errors = validate_listing_data(data)

        assert is_valid is False
        assert "商品名は65文字以内にしてください" in errors

    def test_validate_invalid_duration(self):
        """オークション期間が範囲外の場合"""
        data = {
            "name": "テスト商品",
            "price": 1000,
            "auction_duration": 10,
        }
        is_valid, errors = validate_listing_data(data)

        assert is_valid is False
        assert "オークション期間は1〜7日の範囲で入力してください" in errors

    def test_validate_multiple_errors(self):
        """複数エラーの同時検出"""
        data = {
            "name": None,
            "price": None,
        }
        is_valid, errors = validate_listing_data(data)

        assert is_valid is False
        assert len(errors) >= 2
