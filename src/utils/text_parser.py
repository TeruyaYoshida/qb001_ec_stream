"""
メール解析ロジック
出品依頼メールの本文を解析し、商品情報を抽出する。
"""

import re
from typing import Any, Dict, List, Tuple


def parse_listing_email(body: str) -> Dict[str, Any]:
    """
    メール本文内の定型タグを正規表現で抽出する。
    
    対応タグ:
        - 【商品名】: 商品のタイトル（必須、最大65文字）
        - 【価格】: 開始価格（必須、数値のみ）
        - 【説明】: 商品の詳細説明
        - 【カテゴリ】: ヤフオクカテゴリ名 or ID
        - 【状態】: 商品状態
        - 【配送】: 配送方法
        - 【期間】: オークション期間（1〜7日）
    
    Args:
        body: メール本文
        
    Returns:
        抽出したデータの辞書
    """
    result: Dict[str, Any] = {
        "name": None,
        "price": None,
        "description": "",
        "category": "",
        "condition": "目立った傷や汚れなし",  # デフォルト値
        "shipping_method": "佐川急便",         # デフォルト値
        "auction_duration": 7,                # デフォルト値
    }
    
    # 商品名の抽出（必須）
    name_match = re.search(r'【商品名】\s*(.+?)(?=【|$)', body, re.DOTALL)
    if name_match:
        name = name_match.group(1).strip()
        # 最大65文字に制限
        result["name"] = name[:65] if len(name) > 65 else name
    
    # 価格の抽出（必須）
    price_match = re.search(r'【価格】\s*(\d+)', body)
    if price_match:
        result["price"] = int(price_match.group(1))
    
    # 説明の抽出
    desc_match = re.search(r'【説明】\s*(.+?)(?=【|$)', body, re.DOTALL)
    if desc_match:
        result["description"] = desc_match.group(1).strip()
    
    # カテゴリの抽出
    category_match = re.search(r'【カテゴリ】\s*(.+?)(?=【|$)', body, re.DOTALL)
    if category_match:
        result["category"] = category_match.group(1).strip()
    
    # 状態の抽出
    condition_match = re.search(r'【状態】\s*(.+?)(?=【|$)', body, re.DOTALL)
    if condition_match:
        condition_value = condition_match.group(1).strip()
        # 有効な状態値のリスト
        valid_conditions = [
            "新品、未使用",
            "未使用に近い",
            "目立った傷や汚れなし",
            "やや傷や汚れあり",
            "傷や汚れあり",
            "全体的に状態が悪い",
        ]
        if condition_value in valid_conditions:
            result["condition"] = condition_value
    
    # 配送方法の抽出
    shipping_match = re.search(r'【配送】\s*(.+?)(?=【|$)', body, re.DOTALL)
    if shipping_match:
        shipping_value = shipping_match.group(1).strip()
        # 有効な配送方法のリスト
        valid_shipping = ["佐川急便", "ヤマト運輸", "ゆうパック", "ネコポス"]
        if shipping_value in valid_shipping:
            result["shipping_method"] = shipping_value
    
    # オークション期間の抽出
    duration_match = re.search(r'【期間】\s*(\d+)', body)
    if duration_match:
        duration = int(duration_match.group(1))
        # 1〜7日の範囲に制限
        if 1 <= duration <= 7:
            result["auction_duration"] = duration
    
    return result


def validate_listing_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    必須項目の欠如をチェックする。
    
    必須項目:
        - 商品名（name）
        - 価格（price）
    
    Args:
        data: 検証するデータ辞書
        
    Returns:
        (有効かどうか, エラーメッセージのリスト)
    """
    errors: List[str] = []
    
    # 商品名のチェック
    if not data.get("name"):
        errors.append("商品名が未入力です")
    elif len(data["name"]) > 65:
        errors.append("商品名は65文字以内にしてください")
    
    # 価格のチェック
    if data.get("price") is None:
        errors.append("価格が未入力です")
    elif not isinstance(data["price"], int) or data["price"] <= 0:
        errors.append("価格は正の整数で入力してください")
    
    # オークション期間のチェック
    duration = data.get("auction_duration")
    if duration is not None:
        if not isinstance(duration, int) or not (1 <= duration <= 7):
            errors.append("オークション期間は1〜7日の範囲で入力してください")
    
    return len(errors) == 0, errors
