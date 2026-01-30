# AGENTS.md - Coding Agent Instructions

## Communication Language / コミュニケーション言語
**ユーザーとのやりとりは日本語で行うこと。** コード内のコメントも日本語で記載すること。

## Project Overview
Used clothing sales automation desktop app (中古衣料品販売自動化システム).
Automates Yahoo! Auctions listing, shipping registration (Sagawa Express), and relisting workflows.

**Target:** Windows 10/11, macOS | **Language:** Python 3.10+
**Main Spec:** `docs/system_specification.md` (authoritative technical reference, Japanese)

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| GUI | Flet | 0.21.2 |
| Browser Automation | Playwright (Sync API) | 1.41.0 |
| Email | Google API Client (Gmail API) | 2.111.0 |
| Process Management | psutil | 5.9.7 |
| Distribution | PyInstaller | - |

## Build / Run / Test Commands

### uv環境（推奨）

```bash
# 依存ライブラリのインストール（uv.lockから）
uv sync

# Playwrightブラウザのインストール（初回のみ）
uv run playwright install chromium

# アプリケーション起動
uv run python src/main.py

# テスト実行
uv run pytest                             # 全テスト実行
uv run pytest tests/test_file.py          # 単一ファイル
uv run pytest tests/test_file.py::test_func  # 単一関数
uv run pytest -v -x --tb=short            # 詳細表示、最初の失敗で停止

# 開発用依存関係の追加
uv add --dev pytest
```

### pip環境（代替）

```bash
pip install -r requirements.txt    # Install dependencies
playwright install chromium        # Install browsers (first setup)
python src/main.py                 # Run application
pyinstaller --onefile --windowed src/main.py  # Build executable

# Testing (pytest)
pytest                             # Run all tests
pytest tests/test_file.py          # Single test file
pytest tests/test_file.py::test_func  # Single test function
pytest -v -x --tb=short            # Verbose, stop on first failure
```

## Project Structure

```
src/
├── main.py                # GUI, event handling, thread control
├── config.py              # Settings, path resolution (exe support)
├── models/item.py         # Data models (ListingItem, ShippingRecord)
├── services/
│   ├── gmail_service.py   # Gmail API operations
│   ├── browser_service.py # Playwright browser management
│   ├── auction_service.py # Yahoo! Auctions listing/relisting
│   └── shipping_service.py# Sagawa Express shipping
└── utils/
    ├── logger.py          # Logging (JSON Lines format)
    ├── text_parser.py     # Email parsing logic
    └── file_manager.py    # File/image management
```

## Code Style Guidelines

### Imports (PEP 8 order)
```python
# 1. Standard library
import threading
from pathlib import Path
from typing import List, Optional, Tuple

# 2. Third-party
from playwright.sync_api import sync_playwright, BrowserContext

# 3. Local
from models.item import ListingItem
```

### Type Hints & Data Models
Use type hints for all functions. Use `dataclasses` with `field(default_factory=...)` and `Enum`:
```python
def validate_listing_data(data: dict) -> Tuple[bool, List[str]]: ...

class ItemCondition(Enum):
    NEW = "新品、未使用"
    GOOD = "目立った傷や汚れなし"

@dataclass
class ListingItem:
    name: str
    price: int
    image_paths: List[Path] = field(default_factory=list)
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions/Variables | snake_case | `get_listing_emails` |
| Classes | PascalCase | `ListingItem` |
| Constants | UPPER_SNAKE | `DEFAULT_TIMEOUT_MS` |
| Private | Leading underscore | `_internal_method` |

### Error Handling (Per Workflow)

| Workflow | Strategy | Reason |
|----------|----------|--------|
| Listing (出品) | Skip & Continue | One failure shouldn't stop all |
| Shipping (発送) | Stop Immediately | Prevent mis-delivery |
| Relisting (再出品) | Skip & Continue | One failure shouldn't stop all |

```python
# Listing/Relisting: Skip & Continue
for item in items:
    try:
        process_item(item)
    except Exception as e:
        logger.error(f"Failed: {item.name}", exc_info=True)
        continue

# Shipping: Stop Immediately
try:
    register_shipping(item)
except Exception as e:
    logger.critical(f"Shipping error: {e}")
    raise  # Stop all processing
```

### Threading Model
- **Main thread:** Flet event loop (UI)
- **Worker threads:** Business logic with `threading.Thread(daemon=True)`
- **Communication:** `queue.Queue` for log messages to UI

### Playwright Browser Automation
- Use `launch_persistent_context()` with user's Chrome profile
- Always `headless=False` for debugging and CAPTCHA handling
- Check Chrome conflicts before launch with `psutil`

```python
DEFAULT_TIMEOUT_MS = 30000      # Element wait timeout
NAVIGATION_TIMEOUT_MS = 60000   # Page navigation timeout
MAX_RETRY_COUNT = 3             # Network error retries
RETRY_DELAY_MS = 2000           # Delay between retries
```

### Logging
Format: JSON Lines | Location: `logs/app_YYYY-MM-DD.json` | Rotation: Daily, 30-day retention

## Key Implementation Notes

1. **Stateful Browser Mode:** Use existing Chrome cookies/sessions to avoid 2FA
2. **Chrome Conflict Check:** Warn users to close Chrome before running
3. **Duplicate Prevention:** Track shipped IDs in `data/history/shipped_ids.json`
4. **Image Cleanup:** Auto-delete orphan images older than 24 hours
5. **Gmail Labels:** Mark processed emails with "出品済み" label
6. **Path Resolution:** Use `sys.frozen` check for PyInstaller exe support

## Testing Guidelines
- Framework: pytest
- Test file pattern: `tests/test_*.py`
- Mock external services (Gmail API, Playwright)
- Integration tests with visible browser for critical flows

## Git Commit Messages
Use conventional format: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`

## Documentation Language
All project docs and user-facing strings are in **Japanese**.
Code comments must be in **Japanese**.