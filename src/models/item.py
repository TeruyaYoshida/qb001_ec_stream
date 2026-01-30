"""
データモデル定義
出品商品データおよび発送履歴レコードを定義する。
"""

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
    
    @classmethod
    def from_string(cls, value: str) -> 'ItemCondition':
        """文字列から対応するEnumを取得（デフォルトはGOOD）"""
        for item in cls:
            if item.value == value:
                return item
        return cls.GOOD


class ShippingMethod(Enum):
    """配送方法"""
    SAGAWA = "佐川急便"
    YAMATO = "ヤマト運輸"
    YUPACK = "ゆうパック"
    NEKOPOS = "ネコポス"
    
    @classmethod
    def from_string(cls, value: str) -> 'ShippingMethod':
        """文字列から対応するEnumを取得（デフォルトはSAGAWA）"""
        for item in cls:
            if item.value == value:
                return item
        return cls.SAGAWA


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
    
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            "auction_id": self.auction_id,
            "shipped_at": self.shipped_at,
            "tracking_number": self.tracking_number
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ShippingRecord':
        """辞書から生成"""
        return cls(
            auction_id=data.get("auction_id", ""),
            shipped_at=data.get("shipped_at", ""),
            tracking_number=data.get("tracking_number")
        )
