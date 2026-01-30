"""
Playwright Browser起動テスト

使用方法:
1. config/settings.json でChromeプロファイルパスを設定
2. uv run python tests/integration/test_browser_launch.py を実行
3. ブラウザが起動し、基本動作を確認

注意:
- Chromeが既に起動している場合はエラーになります
- Chromeを閉じてから実行してください
"""

import sys
from pathlib import Path
import time

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from services.browser_service import (
    launch_browser_context,
    check_chrome_running,
    close_browser_context
)
from config import load_settings


def test_browser_launch():
    """ブラウザ起動テスト"""
    print("=== Playwright ブラウザ起動テスト ===\n")
    
    # 設定ファイルの読み込み
    settings = load_settings()
    chrome_profile = settings.get('chrome_profile_path', '')
    
    if not chrome_profile:
        print("エラー: Chromeプロファイルパスが設定されていません")
        print("config/settings.json を編集して chrome_profile_path を設定してください")
        print("\nプロファイルパスの例:")
        print("  macOS: /Users/username/Library/Application Support/Google/Chrome")
        print("  Windows: C:\\Users\\username\\AppData\\Local\\Google\\Chrome\\User Data")
        return False
    
    print(f"Chromeプロファイル: {chrome_profile}")
    
    # Chrome競合チェック
    print("\nChrome競合チェック...")
    if check_chrome_running():
        print("警告: Chromeが既に起動しています")
        print("Chromeを閉じてから再度実行してください")
        return False
    print("✓ Chrome競合なし")
    
    # ブラウザ起動
    print("\nブラウザを起動します...")
    context = None
    page = None
    
    try:
        context = launch_browser_context(chrome_profile)
        print("✓ ブラウザコンテキスト起動成功")
        
        # 新しいページを開く
        page = context.new_page()
        print("✓ 新しいページ作成成功")
        
        # テストページに移動
        print("\nテストページに移動...")
        page.goto('https://www.yahoo.co.jp', timeout=30000)
        print(f"✓ ページタイトル: {page.title()}")
        
        # スクリーンショット取得
        screenshot_path = Path(__file__).parent.parent.parent / 'logs' / 'browser_test.png'
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path))
        print(f"✓ スクリーンショット保存: {screenshot_path}")
        
        # 5秒間表示
        print("\n5秒間ブラウザを表示します...")
        time.sleep(5)
        
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False
    
    finally:
        # クリーンアップ
        print("\nブラウザを閉じます...")
        if page:
            page.close()
        if context:
            close_browser_context(context)
        print("✓ クリーンアップ完了")
    
    print("\n=== すべてのテストが成功しました ===")
    return True


def test_chrome_conflict_detection():
    """Chrome競合検出テスト"""
    print("\n=== Chrome競合検出テスト ===\n")
    
    is_running = check_chrome_running()
    
    if is_running:
        print("検出結果: Chromeが起動中です")
        print("  プロセス名:")
        import psutil
        for proc in psutil.process_iter(['name']):
            name = proc.info['name'].lower()
            if 'chrome' in name or 'google chrome' in name:
                print(f"    - {proc.info['name']}")
    else:
        print("検出結果: Chrome は起動していません")
    
    print(f"\n✓ check_chrome_running() = {is_running}")
    return True


if __name__ == '__main__':
    # Chrome競合検出テスト
    test_chrome_conflict_detection()
    
    print("\n" + "="*50 + "\n")
    
    # ブラウザ起動テスト
    success = test_browser_launch()
    sys.exit(0 if success else 1)
