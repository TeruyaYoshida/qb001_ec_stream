"""
ヤフオク出品・再出品ロジックモジュール
ヤフオク!への出品、未落札商品取得、再出品処理を行う。
"""

import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))
from models.item import ListingItem, ItemCondition
from services.browser_service import with_retry, DEFAULT_TIMEOUT_MS

# ヤフオク関連URL
YAHOO_AUCTION_URL = "https://auctions.yahoo.co.jp/"
YAHOO_AUCTION_SELL_URL = "https://auctions.yahoo.co.jp/sell/jp/show/submit"
YAHOO_AUCTION_MYAUCTION_URL = "https://auctions.yahoo.co.jp/closeduser/jp/show/mystatus"
YAHOO_AUCTION_ENDED_URL = "https://auctions.yahoo.co.jp/closeduser/jp/show/ended"

# ヤフオク出品時のデフォルト設定
DEFAULT_AUCTION_SETTINGS = {
    "auto_extension": True,      # 自動延長: ON
    "early_end": True,           # 早期終了: ON
    "returnable": False,         # 返品不可
    "seller_pays_shipping": True # 出品者負担
}


def list_new_item(context: BrowserContext, item: ListingItem) -> bool:
    """
    新規出品処理を実行する。
    
    取得したデータを各フィールドに入力し、画像をアップロードする。
    エラーが発生した場合は、その商品のみエラーログに記録し、
    次の商品の処理へ進む（スキップ＆継続）。
    
    Args:
        context: Playwrightブラウザコンテキスト
        item: 出品する商品データ
        
    Returns:
        成功時True、失敗時False
    """
    page = context.new_page()
    
    try:
        # 出品ページに遷移
        def navigate():
            page.goto(YAHOO_AUCTION_SELL_URL)
            page.wait_for_load_state("networkidle")
        
        with_retry(navigate)
        
        # ログイン状態の確認
        if not _check_login_status(page):
            raise Exception("ヤフオクにログインしていません")
        
        # 商品名を入力
        name_input = page.locator('input[name="title"], #title')
        if name_input.count() > 0:
            name_input.first.fill(item.name)
        
        # 商品説明を入力
        if item.description:
            desc_input = page.locator('textarea[name="description"], #description')
            if desc_input.count() > 0:
                desc_input.first.fill(item.description)
        
        # カテゴリを選択（カテゴリIDまたは名称が指定されている場合）
        if item.category:
            _select_category(page, item.category)
        
        # 商品状態を選択
        _select_condition(page, item.condition)
        
        # 開始価格を入力
        price_input = page.locator('input[name="startprice"], #startprice')
        if price_input.count() > 0:
            price_input.first.fill(str(item.price))
        
        # オークション期間を設定
        _select_duration(page, item.auction_duration)
        
        # 配送方法を選択
        _select_shipping_method(page, item.shipping_method.value)
        
        # 画像をアップロード
        if item.image_paths:
            _upload_images(page, item.image_paths)
        
        # 自動延長・早期終了を設定
        _set_auction_options(page)
        
        # 確認画面へ進む
        confirm_button = page.locator('button:has-text("確認"), input[type="submit"][value*="確認"]')
        if confirm_button.count() > 0:
            confirm_button.first.click()
            page.wait_for_load_state("networkidle")
        
        # 出品を実行
        submit_button = page.locator('button:has-text("出品"), input[type="submit"][value*="出品"]')
        if submit_button.count() > 0:
            submit_button.first.click()
            page.wait_for_load_state("networkidle")
        
        # 出品完了を確認し、オークションIDを取得
        auction_id = _extract_auction_id(page)
        if auction_id:
            item.auction_id = auction_id
            return True
        
        return False
        
    except Exception as e:
        # エラーをログに記録（呼び出し元でログ出力）
        raise Exception(f"出品エラー ({item.name}): {e}")
        
    finally:
        page.close()


def _check_login_status(page: Page) -> bool:
    """ログイン状態を確認する"""
    # ログインリンクが表示されていたら未ログイン
    login_link = page.locator('a:has-text("ログイン")')
    return login_link.count() == 0


def _select_category(page: Page, category: str) -> None:
    """カテゴリを選択する"""
    # カテゴリ選択ボタンをクリック
    category_button = page.locator('button:has-text("カテゴリ"), a:has-text("カテゴリ選択")')
    if category_button.count() > 0:
        category_button.first.click()
        page.wait_for_timeout(1000)
        
        # カテゴリ名で検索または選択
        category_input = page.locator('input[placeholder*="カテゴリ"]')
        if category_input.count() > 0:
            category_input.first.fill(category)
            page.wait_for_timeout(500)
            
            # サジェストから選択
            suggestion = page.locator(f'.category-item:has-text("{category}")')
            if suggestion.count() > 0:
                suggestion.first.click()


def _select_condition(page: Page, condition: ItemCondition) -> None:
    """商品状態を選択する"""
    condition_select = page.locator('select[name="itemcondition"], #itemcondition')
    if condition_select.count() > 0:
        condition_select.first.select_option(label=condition.value)
    else:
        # ラジオボタン形式の場合
        condition_radio = page.locator(f'input[type="radio"][value*="{condition.value}"]')
        if condition_radio.count() > 0:
            condition_radio.first.click()


def _select_duration(page: Page, days: int) -> None:
    """オークション期間を選択する"""
    duration_select = page.locator('select[name="duration"], #duration')
    if duration_select.count() > 0:
        duration_select.first.select_option(value=str(days))


def _select_shipping_method(page: Page, method: str) -> None:
    """配送方法を選択する"""
    # 送料出品者負担を設定
    seller_pays = page.locator('input[type="radio"][name="shipping_payer"][value="seller"]')
    if seller_pays.count() > 0:
        seller_pays.first.click()
    
    # 配送方法を選択
    shipping_select = page.locator(f'input[type="checkbox"][name*="shipping"][value*="{method}"]')
    if shipping_select.count() > 0:
        if not shipping_select.first.is_checked():
            shipping_select.first.click()


def _upload_images(page: Page, image_paths: List[Path]) -> None:
    """画像をアップロードする"""
    file_input = page.locator('input[type="file"][accept*="image"]')
    if file_input.count() > 0:
        # 複数ファイルを設定
        files = [str(p) for p in image_paths if p.exists()]
        if files:
            file_input.first.set_input_files(files)
            # アップロード完了を待機
            page.wait_for_timeout(2000)


def _set_auction_options(page: Page) -> None:
    """自動延長・早期終了などのオプションを設定する"""
    # 自動延長をON
    auto_extend = page.locator('input[name="autoextend"][type="checkbox"]')
    if auto_extend.count() > 0:
        if not auto_extend.first.is_checked():
            auto_extend.first.click()
    
    # 早期終了をON
    early_end = page.locator('input[name="earlyend"][type="checkbox"]')
    if early_end.count() > 0:
        if not early_end.first.is_checked():
            early_end.first.click()


def _extract_auction_id(page: Page) -> Optional[str]:
    """出品完了ページからオークションIDを抽出する"""
    # URLからIDを抽出
    import re
    url = page.url
    match = re.search(r'/auction/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    
    # ページ内のテキストから抽出
    content = page.content()
    match = re.search(r'オークションID[：:]\s*([a-zA-Z0-9]+)', content)
    if match:
        return match.group(1)
    
    return None


def get_unsold_items(context: BrowserContext) -> List[ListingItem]:
    """
    ヤフオク管理画面から「落札者なしで終了」した商品リストを取得する。
    
    Args:
        context: Playwrightブラウザコンテキスト
        
    Returns:
        未落札商品のリスト
    """
    page = context.new_page()
    unsold_items = []
    
    try:
        # 出品終了分ページに遷移
        def navigate():
            page.goto(YAHOO_AUCTION_ENDED_URL)
            page.wait_for_load_state("networkidle")
        
        with_retry(navigate)
        
        # ログイン状態の確認
        if not _check_login_status(page):
            raise Exception("ヤフオクにログインしていません")
        
        # 「落札者なし」でフィルタリング
        no_bidder_filter = page.locator('a:has-text("落札者なし"), input[value="nobidder"]')
        if no_bidder_filter.count() > 0:
            no_bidder_filter.first.click()
            page.wait_for_load_state("networkidle")
        
        # 商品リストを取得
        items = page.locator('.auction-item, .Product, tr.item-row')
        count = items.count()
        
        for i in range(count):
            item_element = items.nth(i)
            
            # 商品名を取得
            name_element = item_element.locator('.item-name, .Product__title, a.title')
            name = name_element.first.inner_text() if name_element.count() > 0 else ""
            
            # オークションIDを取得
            link_element = item_element.locator('a[href*="/auction/"]')
            auction_id = None
            if link_element.count() > 0:
                href = link_element.first.get_attribute('href')
                if href:
                    import re
                    match = re.search(r'/auction/([a-zA-Z0-9]+)', href)
                    if match:
                        auction_id = match.group(1)
            
            # 価格を取得
            price_element = item_element.locator('.item-price, .Product__price')
            price = 0
            if price_element.count() > 0:
                import re
                price_text = price_element.first.inner_text()
                match = re.search(r'[\d,]+', price_text)
                if match:
                    price = int(match.group().replace(',', ''))
            
            if name and auction_id:
                unsold_items.append(ListingItem(
                    name=name,
                    price=price,
                    auction_id=auction_id
                ))
        
        return unsold_items
        
    except Exception as e:
        raise Exception(f"未落札商品取得エラー: {e}")
        
    finally:
        page.close()


def relist_item(context: BrowserContext, item: ListingItem) -> bool:
    """
    対象商品を再出品処理する。
    
    Args:
        context: Playwrightブラウザコンテキスト
        item: 再出品する商品データ
        
    Returns:
        成功時True、失敗時False
    """
    if not item.auction_id:
        return False
    
    page = context.new_page()
    
    try:
        # 再出品ページに遷移
        relist_url = f"https://auctions.yahoo.co.jp/sell/jp/show/relist?aID={item.auction_id}"
        
        def navigate():
            page.goto(relist_url)
            page.wait_for_load_state("networkidle")
        
        with_retry(navigate)
        
        # ログイン状態の確認
        if not _check_login_status(page):
            raise Exception("ヤフオクにログインしていません")
        
        # 確認画面へ進む
        confirm_button = page.locator('button:has-text("確認"), input[type="submit"][value*="確認"]')
        if confirm_button.count() > 0:
            confirm_button.first.click()
            page.wait_for_load_state("networkidle")
        
        # 再出品を実行
        submit_button = page.locator('button:has-text("再出品"), input[type="submit"][value*="出品"]')
        if submit_button.count() > 0:
            submit_button.first.click()
            page.wait_for_load_state("networkidle")
        
        # 新しいオークションIDを取得
        new_auction_id = _extract_auction_id(page)
        if new_auction_id:
            item.auction_id = new_auction_id
            return True
        
        return False
        
    except Exception as e:
        raise Exception(f"再出品エラー ({item.name}): {e}")
        
    finally:
        page.close()


def relist_all_unsold(context: BrowserContext) -> Tuple[int, int]:
    """
    全ての未落札商品を順次再出品する。
    
    Args:
        context: Playwrightブラウザコンテキスト
        
    Returns:
        (成功件数, スキップ件数)
    """
    unsold_items = get_unsold_items(context)
    
    success_count = 0
    skip_count = 0
    
    for item in unsold_items:
        try:
            if relist_item(context, item):
                success_count += 1
            else:
                skip_count += 1
        except Exception:
            # エラー発生時はスキップして続行
            skip_count += 1
            continue
    
    return success_count, skip_count
