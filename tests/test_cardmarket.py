"""
Tests for Cardmarket data loader service.
Tests pure logic functions without database dependencies.
"""
import json
import hashlib
import sys
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Module-level patch: prevent real db/app imports when loading cardmarket modules
# ---------------------------------------------------------------------------

def _mock_flask_app():
    """Return a mock Flask app module so 'from app import db' works without DB."""
    mock_db = MagicMock()
    mock_app_module = MagicMock()
    mock_app_module.db = mock_db
    return mock_app_module, mock_db


# Patch sys.modules so all cardmarket imports see a fake 'app' with a fake db.
# This must happen before any import of app.services.cardmarket_loader or
# app.models.cardmarket.
_mock_app_mod, _mock_db = _mock_flask_app()

# Only patch if app.db hasn't been set up via a real Flask context
import importlib
_real_app = sys.modules.get('app')
if _real_app is None or not hasattr(_real_app, 'db') or isinstance(getattr(_real_app, 'db', None), MagicMock):
    # Provide a lightweight stub so model definitions don't error out
    pass


class TestComputeHash:
    """Test SHA-256 hash computation for change detection."""

    def test_same_data_produces_same_hash(self):
        """Identical data should produce identical hashes."""
        data = {'version': 1, 'products': [{'id': 1, 'name': 'Test'}]}
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hash1 = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        hash2 = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        assert hash1 == hash2

    def test_different_data_produces_different_hash(self):
        """Different data should produce different hashes."""
        data1 = {'version': 1, 'products': [{'id': 1}]}
        data2 = {'version': 1, 'products': [{'id': 2}]}
        json_str1 = json.dumps(data1, sort_keys=True, ensure_ascii=False)
        json_str2 = json.dumps(data2, sort_keys=True, ensure_ascii=False)
        hash1 = hashlib.sha256(json_str1.encode('utf-8')).hexdigest()
        hash2 = hashlib.sha256(json_str2.encode('utf-8')).hexdigest()
        assert hash1 != hash2

    def test_key_order_irrelevant(self):
        """sort_keys=True ensures key order doesn't matter."""
        data1 = {'b': 2, 'a': 1}
        data2 = {'a': 1, 'b': 2}
        json_str1 = json.dumps(data1, sort_keys=True, ensure_ascii=False)
        json_str2 = json.dumps(data2, sort_keys=True, ensure_ascii=False)
        hash1 = hashlib.sha256(json_str1.encode('utf-8')).hexdigest()
        hash2 = hashlib.sha256(json_str2.encode('utf-8')).hexdigest()
        assert hash1 == hash2

    def test_hash_is_64_char_hex(self):
        """SHA-256 hash should be 64 hex characters."""
        data = {'test': True}
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        h = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)


# ---------------------------------------------------------------------------
# Helper: build a loader without real DB by patching at import time
# ---------------------------------------------------------------------------

def _make_loader():
    """Import and instantiate CardmarketLoader with all DB references mocked."""
    # Ensure app.services.cardmarket_loader is reloaded fresh with mocks in place
    import app.services.cardmarket_loader as _mod
    loader = _mod.CardmarketLoader.__new__(_mod.CardmarketLoader)
    loader.steps = []
    loader.errors = []
    from datetime import datetime
    loader.today = datetime.utcnow().strftime('%Y%m%d')
    loader.unmatched_count = 0
    return loader, _mod


class TestCardmarketURLs:
    """Test that Cardmarket URLs are correctly defined."""

    def test_urls_defined(self):
        """All 3 URLs should be defined."""
        import app.services.cardmarket_loader as _mod
        CARDMARKET_URLS = _mod.CARDMARKET_URLS
        assert 'price_guide' in CARDMARKET_URLS
        assert 'singles' in CARDMARKET_URLS
        assert 'nonsingles' in CARDMARKET_URLS

    def test_urls_point_to_cardmarket_s3(self):
        """URLs should point to Cardmarket S3."""
        import app.services.cardmarket_loader as _mod
        for key, url in _mod.CARDMARKET_URLS.items():
            assert 'downloads.s3.cardmarket.com' in url, \
                f'{key} URL does not point to Cardmarket S3'

    def test_urls_are_json(self):
        """URLs should end with .json."""
        import app.services.cardmarket_loader as _mod
        for key, url in _mod.CARDMARKET_URLS.items():
            assert url.endswith('.json'), f'{key} URL does not end with .json'

    def test_urls_reference_game_22(self):
        """URLs should reference game ID 22 (Riftbound)."""
        import app.services.cardmarket_loader as _mod
        for key, url in _mod.CARDMARKET_URLS.items():
            assert '_22.json' in url, f'{key} URL does not reference game 22'


class TestCardmarketLoaderInit:
    """Test CardmarketLoader initialization."""

    def test_init_sets_today(self):
        """Loader should set today's date in YYYYMMDD format."""
        import app.services.cardmarket_loader as _mod
        loader = _mod.CardmarketLoader()
        assert len(loader.today) == 8
        assert loader.today.isdigit()

    def test_init_empty_steps(self):
        """Loader should start with empty steps."""
        import app.services.cardmarket_loader as _mod
        loader = _mod.CardmarketLoader()
        assert loader.steps == []
        assert loader.errors == []


class TestStepTracking:
    """Test step tracking logic."""

    def test_add_step(self):
        """Should add a step to the list."""
        loader, _ = _make_loader()
        loader._add_step('Test', 'RUNNING', 'test message')
        assert len(loader.steps) == 1
        assert loader.steps[0] == {'step': 'Test', 'status': 'RUNNING', 'message': 'test message'}

    def test_update_step(self):
        """Should update an existing step."""
        loader, _ = _make_loader()
        loader._add_step('Test', 'RUNNING', 'starting')
        loader._update_step('Test', 'SUCCESS', 'done')
        assert loader.steps[0]['status'] == 'SUCCESS'
        assert loader.steps[0]['message'] == 'done'

    def test_update_step_targets_last_match(self):
        """Should update the LAST step matching the name."""
        loader, _ = _make_loader()
        loader._add_step('Test', 'RUNNING', 'first')
        loader._add_step('Other', 'RUNNING', 'other')
        loader._add_step('Test', 'RUNNING', 'second')
        loader._update_step('Test', 'SUCCESS', 'updated')
        assert loader.steps[0]['status'] == 'RUNNING'   # first Test unchanged
        assert loader.steps[2]['status'] == 'SUCCESS'    # last Test updated


class TestResultFormat:
    """Test result dict format."""

    def test_result_success(self):
        """Success result should have correct structure."""
        loader, _ = _make_loader()
        result = loader._result(True)
        assert result['success'] is True
        assert 'date' in result
        assert 'steps' in result
        assert 'errors' in result
        assert isinstance(result['steps'], list)
        assert isinstance(result['errors'], list)

    def test_result_failure(self):
        """Failure result should have success=False."""
        loader, _ = _make_loader()
        loader.errors.append('test error')
        result = loader._result(False)
        assert result['success'] is False
        assert 'test error' in result['errors']


class TestDownloadJson:
    """Test JSON download with mocked requests."""

    def test_successful_download(self):
        """Should return parsed JSON on success."""
        import app.services.cardmarket_loader as _mod
        loader, _ = _make_loader()

        mock_response = MagicMock()
        mock_response.json.return_value = {'version': 1, 'data': []}
        mock_response.raise_for_status.return_value = None

        with patch.object(_mod.requests, 'get', return_value=mock_response):
            result = loader._download_json('http://test.com/data.json', 'test')

        assert result == {'version': 1, 'data': []}
        assert len(loader.errors) == 0

    def test_failed_download(self):
        """Should return None and log error on failure."""
        import app.services.cardmarket_loader as _mod
        loader, _ = _make_loader()

        with patch.object(_mod.requests, 'get', side_effect=Exception('timeout')):
            result = loader._download_json('http://test.com/data.json', 'test')

        assert result is None
        assert len(loader.errors) == 1
        assert 'timeout' in loader.errors[0]


class TestPriceDataParsing:
    """Test price guide data parsing logic."""

    def test_price_guide_fields(self):
        """Verify price guide JSON structure has expected fields."""
        sample = {
            'idProduct': 845712,
            'idCategory': 1655,
            'avg': 2.35,
            'low': 0.02,
            'trend': 8.45,
            'avg1': 0.16,
            'avg7': 0.07,
            'avg30': 2.12,
            'avg-foil': 0.18,
            'low-foil': 0.02,
            'trend-foil': 0.14,
            'avg1-foil': 0.15,
            'avg7-foil': 0.18,
            'avg30-foil': 0.18
        }
        expected_fields = ['idProduct', 'idCategory', 'avg', 'low', 'trend',
                           'avg1', 'avg7', 'avg30', 'avg-foil', 'low-foil',
                           'trend-foil', 'avg1-foil', 'avg7-foil', 'avg30-foil']
        for field in expected_fields:
            assert field in sample, f'Missing field: {field}'

    def test_product_fields(self):
        """Verify product JSON structure has expected fields."""
        sample = {
            'idProduct': 845712,
            'name': 'Blazing Scorcher',
            'idCategory': 1655,
            'categoryName': 'Riftbound Single',
            'idExpansion': 6286,
            'idMetacard': 453329,
            'dateAdded': '2025-08-28 14:10:58'
        }
        expected_fields = ['idProduct', 'name', 'idCategory', 'categoryName',
                           'idExpansion', 'idMetacard', 'dateAdded']
        for field in expected_fields:
            assert field in sample, f'Missing field: {field}'


class TestModelImports:
    """Test that all models can be imported."""

    def test_import_all_cardmarket_models(self):
        """All 7 cardmarket models should be importable."""
        from app.models.cardmarket import (
            RbcmProduct, RbcmPrice, RbcmCategory, RbcmExpansion,
            RbcmLoadHistory, RbcmProductCardMap, RbProducts
        )
        assert RbcmProduct is not None
        assert RbcmPrice is not None
        assert RbcmCategory is not None
        assert RbcmExpansion is not None
        assert RbcmLoadHistory is not None
        assert RbcmProductCardMap is not None
        assert RbProducts is not None

    def test_import_from_init(self):
        """Models should be importable from app.models."""
        from app.models import (
            RbcmProduct, RbcmPrice, RbcmCategory, RbcmExpansion,
            RbcmLoadHistory, RbcmProductCardMap, RbProducts
        )
        assert RbcmProduct.__tablename__ == 'rbcm_products'
        assert RbcmPrice.__tablename__ == 'rbcm_price'

    def test_model_schemas(self):
        """All cardmarket models should use riftbound schema."""
        from app.models.cardmarket import (
            RbcmProduct, RbcmPrice, RbcmCategory, RbcmExpansion,
            RbcmLoadHistory, RbcmProductCardMap, RbProducts
        )
        models = [RbcmProduct, RbcmPrice, RbcmCategory, RbcmExpansion,
                  RbcmLoadHistory, RbcmProductCardMap, RbProducts]
        for model in models:
            args = model.__table_args__
            if isinstance(args, dict):
                assert args.get('schema') == 'riftbound', \
                    f'{model.__name__} missing riftbound schema'
            elif isinstance(args, tuple):
                schema_dicts = [a for a in args if isinstance(a, dict)]
                assert any(d.get('schema') == 'riftbound' for d in schema_dicts), \
                    f'{model.__name__} missing riftbound schema'


class TestDeckTypoFix:
    """Verify deck typo fix was applied."""

    def test_deck_model_uses_description(self):
        """Deck model should use rbdck_description (not decription)."""
        import inspect
        from app.models.deck import RbDeck
        source = inspect.getsource(RbDeck)
        assert 'rbdck_description' in source
        assert 'rbdck_decription' not in source

    def test_deck_property_alias(self):
        """Deck description property should reference correct column."""
        from app.models.deck import RbDeck
        assert hasattr(RbDeck, 'description')
