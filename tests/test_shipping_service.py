"""
shipping_service.py のユニットテスト
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from playwright.sync_api import Page, BrowserContext

# テスト対象モジュールをインポート
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.shipping_service import (
    _login_to_smart_club,
    _handle_first_time_access,
    _navigate_to_ehiden3,
    SAGAWA_SMART_CLUB_LOGIN_URL,
    SELECTOR_BUSINESS_TAB,
    SELECTOR_USER_ID,
    SELECTOR_PASSWORD,
    SELECTOR_LOGIN_BUTTON,
)


class TestLoginToSmartClub:
    """スマートクラブログイン処理のテスト"""

    def test_login_success(self):
        """正常系: ログインが成功する"""
        # モックページを作成
        mock_page = Mock(spec=Page)
        mock_page.url = SAGAWA_SMART_CLUB_LOGIN_URL

        # モックロケータを作成
        mock_business_tab = Mock()
        mock_business_tab.count.return_value = 1

        mock_user_id_input = Mock()
        mock_user_id_input.count.return_value = 1

        mock_password_input = Mock()
        mock_password_input.count.return_value = 1

        mock_login_button = Mock()
        mock_login_button.count.return_value = 1

        mock_error_message = Mock()
        mock_error_message.count.return_value = 0

        # locatorメソッドの戻り値を設定
        def locator_side_effect(selector):
            if selector == SELECTOR_BUSINESS_TAB:
                return mock_business_tab
            elif selector == SELECTOR_USER_ID:
                return mock_user_id_input
            elif selector == SELECTOR_PASSWORD:
                return mock_password_input
            elif selector == SELECTOR_LOGIN_BUTTON:
                return mock_login_button
            elif '.error' in selector:
                return mock_error_message
            return Mock()

        mock_page.locator.side_effect = locator_side_effect

        # 環境変数を設定
        with patch.dict(os.environ, {
            'SAGAWA_USER_ID': 'test_user',
            'SAGAWA_PASSWORD': 'test_password'
        }):
            # テスト実行
            _login_to_smart_club(mock_page)

        # 検証
        mock_business_tab.first.click.assert_called_once()
        mock_user_id_input.fill.assert_called_once_with('test_user')
        mock_password_input.fill.assert_called_once_with('test_password')
        mock_login_button.click.assert_called_once()
        mock_page.wait_for_load_state.assert_called()

    def test_login_missing_credentials(self):
        """異常系: 認証情報が設定されていない"""
        mock_page = Mock(spec=Page)
        mock_page.url = SAGAWA_SMART_CLUB_LOGIN_URL

        # 環境変数をクリア
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                _login_to_smart_club(mock_page)

            assert "認証情報が設定されていません" in str(exc_info.value)

    def test_login_already_logged_in(self):
        """正常系: 既にログイン済みの場合はスキップ"""
        mock_page = Mock(spec=Page)
        mock_page.url = "https://www.e-service.sagawa-exp.co.jp/portal/dashboard"

        with patch.dict(os.environ, {
            'SAGAWA_USER_ID': 'test_user',
            'SAGAWA_PASSWORD': 'test_password'
        }):
            # テスト実行
            _login_to_smart_club(mock_page)

        # ログインページではないので、locatorは呼ばれない
        mock_page.locator.assert_not_called()


class TestHandleFirstTimeAccess:
    """初回アクセス処理のテスト"""

    def test_handle_agree_button(self):
        """正常系: 同意ボタンが表示されている場合"""
        mock_page = Mock(spec=Page)

        mock_agree_button = Mock()
        mock_agree_button.count.return_value = 1

        mock_close_button = Mock()
        mock_close_button.count.return_value = 0

        def locator_side_effect(selector):
            if '同意' in selector:
                return mock_agree_button
            elif '閉じる' in selector:
                return mock_close_button
            return Mock()

        mock_page.locator.side_effect = locator_side_effect

        # テスト実行
        _handle_first_time_access(mock_page)

        # 検証
        mock_agree_button.first.click.assert_called_once()
        mock_page.wait_for_load_state.assert_called()

    def test_handle_no_popups(self):
        """正常系: ポップアップが表示されていない場合"""
        mock_page = Mock(spec=Page)

        mock_agree_button = Mock()
        mock_agree_button.count.return_value = 0

        mock_close_button = Mock()
        mock_close_button.count.return_value = 0

        def locator_side_effect(selector):
            if '同意' in selector:
                return mock_agree_button
            elif '閉じる' in selector:
                return mock_close_button
            return Mock()

        mock_page.locator.side_effect = locator_side_effect

        # テスト実行（エラーが発生しないことを確認）
        _handle_first_time_access(mock_page)


class TestNavigateToEhiden3:
    """e飛伝Ⅲへの遷移処理のテスト"""

    def test_navigate_success(self):
        """正常系: e飛伝Ⅲメニューが見つかる"""
        mock_page = Mock(spec=Page)

        mock_ehiden_menu = Mock()
        mock_ehiden_menu.count.return_value = 1

        mock_page.locator.return_value = mock_ehiden_menu

        # テスト実行
        _navigate_to_ehiden3(mock_page)

        # 検証
        mock_ehiden_menu.first.click.assert_called_once()
        mock_page.wait_for_load_state.assert_called()

    def test_navigate_menu_not_found(self):
        """異常系: e飛伝Ⅲメニューが見つからない"""
        mock_page = Mock(spec=Page)

        mock_ehiden_menu = Mock()
        mock_ehiden_menu.count.return_value = 0

        mock_page.locator.return_value = mock_ehiden_menu

        # テスト実行
        with pytest.raises(Exception) as exc_info:
            _navigate_to_ehiden3(mock_page)

        assert "e飛伝Ⅲメニューが見つかりません" in str(exc_info.value)
