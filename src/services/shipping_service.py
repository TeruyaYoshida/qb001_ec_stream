"""
発送ロジック・重複防止モジュール
「発送」業務フローの実行。佐川急便e飛伝Webへの送り状登録を行う。
重複登録の防止処理を含む。
"""

import re
import sys
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import BrowserContext, Page

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))
from models.item import ListingItem
from services.browser_service import with_retry
from utils.file_manager import load_shipped_history, save_shipped_id

# ヤフオク取引ナビURL
YAHOO_AUCTION_TRANSACTION_URL = "https://contact.auctions.yahoo.co.jp/seller/top"

# 佐川急便e飛伝WebのURL
SAGAWA_EHIDEN_URL = "https://www.e-hiden.net/ehiden/"


def get_sold_items(context: BrowserContext) -> List[ListingItem]:
    """
    ヤフオク管理画面（マイオク > 落札分 > 取引ナビ）から情報を取得する。
    
    対象: 「支払い完了」かつ「未発送」ステータスの商品。
    取得後、履歴照合を行い、既に処理済みの商品はリストから除外する。
    
    Args:
        context: Playwrightブラウザコンテキスト
        
    Returns:
        発送対象商品のリスト
    """
    page = context.new_page()
    sold_items = []
    
    try:
        # 取引ナビページに遷移
        def navigate():
            page.goto(YAHOO_AUCTION_TRANSACTION_URL)
            page.wait_for_load_state("networkidle")
        
        with_retry(navigate)
        
        # ログイン状態の確認
        login_link = page.locator('a:has-text("ログイン")')
        if login_link.count() > 0:
            raise Exception("ヤフオクにログインしていません")
        
        # 発送済み履歴を読み込む
        shipped_ids = load_shipped_history()
        
        # 「支払い完了」「未発送」でフィルタリング
        paid_filter = page.locator('select[name="status"], #status-filter')
        if paid_filter.count() > 0:
            paid_filter.first.select_option(label="支払い完了")
            page.wait_for_load_state("networkidle")
        
        # 取引リストを取得
        transactions = page.locator('.transaction-item, .Product, tr.transaction-row')
        count = transactions.count()
        
        for i in range(count):
            item_element = transactions.nth(i)
            
            # オークションIDを取得
            link_element = item_element.locator('a[href*="/auction/"], a[href*="aID="]')
            auction_id = None
            if link_element.count() > 0:
                href = link_element.first.get_attribute('href')
                if href:
                    # URLからオークションIDを抽出
                    match = re.search(r'/auction/([a-zA-Z0-9]+)', href)
                    if not match:
                        match = re.search(r'aID=([a-zA-Z0-9]+)', href)
                    if match:
                        auction_id = match.group(1)
            
            # 履歴にあるIDはスキップ
            if auction_id and auction_id in shipped_ids:
                continue
            
            # 商品名を取得
            name_element = item_element.locator('.item-name, .Product__title, a.title')
            name = name_element.first.inner_text() if name_element.count() > 0 else ""
            
            # 価格を取得
            price_element = item_element.locator('.item-price, .Product__price')
            price = 0
            if price_element.count() > 0:
                price_text = price_element.first.inner_text()
                match = re.search(r'[\d,]+', price_text)
                if match:
                    price = int(match.group().replace(',', ''))
            
            # 取引ナビから購入者情報を取得
            buyer_info = _get_buyer_info(page, item_element, auction_id)
            
            if name and auction_id:
                item = ListingItem(
                    name=name,
                    price=price,
                    auction_id=auction_id,
                    buyer_name=buyer_info.get('name'),
                    buyer_address=buyer_info.get('address'),
                    buyer_phone=buyer_info.get('phone'),
                    buyer_postal_code=buyer_info.get('postal_code'),
                )
                sold_items.append(item)
        
        return sold_items
        
    except Exception as e:
        raise Exception(f"落札商品取得エラー: {e}")
        
    finally:
        page.close()


def _get_buyer_info(page: Page, item_element, auction_id: Optional[str]) -> dict:
    """
    取引ナビから購入者情報を取得する。
    
    Args:
        page: Playwrightページオブジェクト
        item_element: 商品要素
        auction_id: オークションID
        
    Returns:
        購入者情報の辞書
    """
    buyer_info = {
        'name': None,
        'address': None,
        'phone': None,
        'postal_code': None,
    }
    
    try:
        # 取引詳細ページへのリンクをクリック
        detail_link = item_element.locator('a:has-text("取引ナビ"), a:has-text("詳細")')
        if detail_link.count() > 0:
            # 新しいタブで開かないように
            href = detail_link.first.get_attribute('href')
            if href:
                detail_page = page.context.new_page()
                try:
                    detail_page.goto(href)
                    detail_page.wait_for_load_state("networkidle")
                    
                    # 購入者氏名を取得
                    name_element = detail_page.locator('.buyer-name, [data-testid="buyer-name"]')
                    if name_element.count() > 0:
                        buyer_info['name'] = name_element.first.inner_text().strip()
                    
                    # 配送先住所を取得
                    address_element = detail_page.locator('.shipping-address, [data-testid="shipping-address"]')
                    if address_element.count() > 0:
                        buyer_info['address'] = address_element.first.inner_text().strip()
                    
                    # 電話番号を取得
                    phone_element = detail_page.locator('.buyer-phone, [data-testid="buyer-phone"]')
                    if phone_element.count() > 0:
                        buyer_info['phone'] = phone_element.first.inner_text().strip()
                    
                    # 郵便番号を取得
                    postal_element = detail_page.locator('.postal-code, [data-testid="postal-code"]')
                    if postal_element.count() > 0:
                        buyer_info['postal_code'] = postal_element.first.inner_text().strip()
                    
                finally:
                    detail_page.close()
    
    except Exception:
        # 取得エラーは無視（必須ではない情報）
        pass
    
    return buyer_info


def register_shipping(context: BrowserContext, item: ListingItem) -> bool:
    """
    佐川急便「e飛伝Web」へアクセスし、送り状発行データを登録する。
    
    登録成功後、即座にそのオークションIDを履歴ファイルへ書き込む。
    これにより、実行中にアプリが落ちても再開時の重複を防ぐ。
    
    重要: 住所不備やシステムエラー発生時は、例外を送出し、処理を中断する
    （スキップしない）。
    
    Args:
        context: Playwrightブラウザコンテキスト
        item: 発送対象商品データ
        
    Returns:
        成功時True
        
    Raises:
        Exception: 登録に失敗した場合（住所不備、システムエラー等）
    """
    if not item.auction_id:
        raise ValueError("オークションIDが設定されていません")
    
    # 必須項目の確認
    if not item.buyer_name:
        raise ValueError(f"購入者氏名が取得できていません (商品: {item.name})")
    
    if not item.buyer_address:
        raise ValueError(f"配送先住所が取得できていません (商品: {item.name})")
    
    page = context.new_page()
    
    try:
        # e飛伝Webにアクセス
        def navigate():
            page.goto(SAGAWA_EHIDEN_URL)
            page.wait_for_load_state("networkidle")
        
        with_retry(navigate)
        
        # ログイン状態の確認
        login_form = page.locator('form[action*="login"], #login-form')
        if login_form.count() > 0:
            raise Exception("e飛伝Webにログインしていません")
        
        # 送り状発行メニューへ遷移
        create_menu = page.locator('a:has-text("送り状発行"), a:has-text("新規作成")')
        if create_menu.count() > 0:
            create_menu.first.click()
            page.wait_for_load_state("networkidle")
        
        # お届け先情報を入力
        # 郵便番号
        if item.buyer_postal_code:
            postal_input = page.locator('input[name="postal_code"], input[name="zip"], #postal-code')
            if postal_input.count() > 0:
                # ハイフンを除去
                postal_code = item.buyer_postal_code.replace('-', '').replace('−', '')
                postal_input.first.fill(postal_code)
        
        # 住所
        address_input = page.locator('input[name="address"], textarea[name="address"], #address')
        if address_input.count() > 0:
            address_input.first.fill(item.buyer_address)
        
        # 氏名
        name_input = page.locator('input[name="name"], input[name="recipient_name"], #name')
        if name_input.count() > 0:
            name_input.first.fill(item.buyer_name)
        
        # 電話番号
        if item.buyer_phone:
            phone_input = page.locator('input[name="phone"], input[name="tel"], #phone')
            if phone_input.count() > 0:
                # ハイフンを除去
                phone = item.buyer_phone.replace('-', '').replace('−', '')
                phone_input.first.fill(phone)
        
        # 品名（商品名）
        product_input = page.locator('input[name="product_name"], input[name="item"], #product-name')
        if product_input.count() > 0:
            # 品名は「衣類」等の一般的な表記が望ましい場合もある
            product_input.first.fill("衣類")
        
        # 確認画面へ進む
        confirm_button = page.locator('button:has-text("確認"), input[type="submit"][value*="確認"]')
        if confirm_button.count() > 0:
            confirm_button.first.click()
            page.wait_for_load_state("networkidle")
        
        # エラーメッセージがないか確認
        error_message = page.locator('.error, .alert-danger, [class*="error"]')
        if error_message.count() > 0:
            error_text = error_message.first.inner_text()
            raise Exception(f"e飛伝登録エラー: {error_text}")
        
        # 登録を実行
        submit_button = page.locator('button:has-text("登録"), input[type="submit"][value*="登録"]')
        if submit_button.count() > 0:
            submit_button.first.click()
            page.wait_for_load_state("networkidle")
        
        # 送り状番号（追跡番号）を取得
        tracking_number = _extract_tracking_number(page)
        
        # 完了確認（エラーがないか）
        error_message = page.locator('.error, .alert-danger, [class*="error"]')
        if error_message.count() > 0:
            error_text = error_message.first.inner_text()
            raise Exception(f"e飛伝登録エラー: {error_text}")
        
        # 登録成功：即座に履歴ファイルへ書き込む
        save_shipped_id(item.auction_id, tracking_number)
        
        return True
        
    except Exception as e:
        # 発送業務のエラーは即時停止のため、例外を再送出
        raise Exception(f"発送登録エラー ({item.name}): {e}")
        
    finally:
        page.close()


def _extract_tracking_number(page: Page) -> Optional[str]:
    """
    登録完了ページから送り状番号（追跡番号）を抽出する。
    
    Args:
        page: Playwrightページオブジェクト
        
    Returns:
        送り状番号、または取得できない場合None
    """
    # ページ内から追跡番号を抽出
    tracking_element = page.locator('.tracking-number, [data-testid="tracking-number"], .slip-number')
    if tracking_element.count() > 0:
        return tracking_element.first.inner_text().strip()
    
    # テキストから正規表現で抽出
    content = page.content()
    match = re.search(r'送り状番号[：:]\s*(\d{10,12})', content)
    if match:
        return match.group(1)
    
    match = re.search(r'追跡番号[：:]\s*(\d{10,12})', content)
    if match:
        return match.group(1)
    
    return None
