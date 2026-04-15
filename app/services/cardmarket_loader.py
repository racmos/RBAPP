"""
Cardmarket data loader service.
Downloads product catalogs and price guides from Cardmarket S3,
validates changes via SHA-256, and loads to PostgreSQL tables.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

import requests
from app import db
from app.models.cardmarket import (
    RbcmProduct, RbcmPrice, RbcmCategory, RbcmExpansion,
    RbcmLoadHistory, RbcmProductCardMap, RbProducts
)

logger = logging.getLogger(__name__)

CARDMARKET_URLS = {
    'price_guide': 'https://downloads.s3.cardmarket.com/productCatalog/priceGuide/price_guide_22.json',
    'singles': 'https://downloads.s3.cardmarket.com/productCatalog/productList/products_singles_22.json',
    'nonsingles': 'https://downloads.s3.cardmarket.com/productCatalog/productList/products_nonsingles_22.json',
}


class CardmarketLoader:
    """Orchestrates download, validation, and loading of Cardmarket data."""

    def __init__(self):
        self.steps = []
        self.errors = []
        self.today = datetime.utcnow().strftime('%Y%m%d')
        self.unmatched_count = 0

    def run(self, urls: Optional[dict] = None) -> dict:
        """Main orchestrator. Downloads, validates, loads all 3 files.

        Returns dict: {success: bool, steps: list, errors: list}
        """
        urls = urls or CARDMARKET_URLS

        try:
            # Step 1: Download all 3 files
            self._add_step('Download', 'RUNNING', 'Downloading files from Cardmarket...')

            price_data = self._download_json(urls['price_guide'], 'price_guide')
            singles_data = self._download_json(urls['singles'], 'singles')
            nonsingles_data = self._download_json(urls['nonsingles'], 'nonsingles')

            if not all([price_data, singles_data, nonsingles_data]):
                self._update_step('Download', 'ERROR', 'Failed to download one or more files')
                return self._result(False)

            self._update_step('Download', 'SUCCESS', 'All 3 files downloaded successfully')

            # Step 2: Compute hashes for change detection
            self._add_step('Validation', 'RUNNING', 'Checking for changes...')

            price_hash = self._compute_hash(price_data)
            singles_hash = self._compute_hash(singles_data)
            nonsingles_hash = self._compute_hash(nonsingles_data)

            # Price guide ALWAYS loads daily
            price_should_load = True
            price_already = self._check_already_loaded('price_guide', price_hash)
            if price_already:
                price_should_load = True  # still load — requirement says always daily
                self._update_step('Validation', 'INFO',
                                  'Price guide already loaded today but will reload (daily requirement)')

            # Products only load if content changed
            singles_should_load = not self._check_already_loaded('singles', singles_hash)
            nonsingles_should_load = not self._check_already_loaded('nonsingles', nonsingles_hash)

            validation_msg = []
            if not singles_should_load:
                validation_msg.append('Singles: no changes')
            if not nonsingles_should_load:
                validation_msg.append('Non-singles: no changes')
            validation_msg.append(f'Price guide: {"reload" if price_already else "new load"}')

            self._update_step('Validation', 'SUCCESS', '; '.join(validation_msg))

            # Step 3: Load categories & expansions (from products data)
            if singles_should_load or nonsingles_should_load:
                self._add_step('Categories & Expansions', 'RUNNING', 'Loading lookup tables...')
                all_products = []
                if singles_should_load:
                    all_products.extend(singles_data.get('products', []))
                if nonsingles_should_load:
                    all_products.extend(nonsingles_data.get('products', []))

                cat_count = self._extract_categories(all_products)
                exp_count = self._extract_expansions(all_products)
                self._update_step('Categories & Expansions', 'SUCCESS',
                                  f'{cat_count} categories, {exp_count} expansions loaded')

            # Step 4: Load products
            products_loaded = 0
            if singles_should_load or nonsingles_should_load:
                self._add_step('Products', 'RUNNING', 'Loading product data...')

                if singles_should_load:
                    count = self._load_products(singles_data.get('products', []), 'single')
                    products_loaded += count
                    self._record_history('singles', singles_hash, count, 'success',
                                         f'Loaded {count} singles')

                if nonsingles_should_load:
                    count = self._load_products(nonsingles_data.get('products', []), 'nonsingle')
                    products_loaded += count
                    self._record_history('nonsingles', nonsingles_hash, count, 'success',
                                         f'Loaded {count} nonsingles')

                self._update_step('Products', 'SUCCESS', f'{products_loaded} products loaded')
            else:
                self._add_step('Products', 'SKIPPED', 'No changes detected in product files')
                self._record_history('singles', singles_hash, 0, 'skipped', 'No changes')
                self._record_history('nonsingles', nonsingles_hash, 0, 'skipped', 'No changes')

            # Step 5: Load prices (always daily)
            self._add_step('Prices', 'RUNNING', 'Loading price data...')
            price_count = self._load_prices(price_data.get('priceGuides', []))
            self._record_history('price_guide', price_hash, price_count, 'success',
                                 f'Loaded {price_count} price records')
            self._update_step('Prices', 'SUCCESS', f'{price_count} price records loaded')

            # Step 6: Auto-map products to internal cards
            self._add_step('Product Mapping', 'RUNNING', 'Auto-mapping products to cards...')
            map_counts = self._update_product_card_map()
            self.unmatched_count = map_counts['unmatched']
            map_msg = (f"{map_counts['auto_matched']} auto-matched, "
                       f"{map_counts['unmatched']} unmatched, "
                       f"{map_counts['already_mapped']} already mapped")
            self._update_step('Product Mapping', 'SUCCESS', map_msg)

            db.session.commit()

            return self._result(True)

        except Exception as e:
            db.session.rollback()
            logger.error(f'Cardmarket load failed: {e}', exc_info=True)
            self.errors.append(str(e))
            return self._result(False)

    def _download_json(self, url: str, file_type: str) -> Optional[dict]:
        """Download JSON file from URL."""
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f'Failed to download {file_type} from {url}: {e}')
            self.errors.append(f'Download failed for {file_type}: {str(e)}')
            return None

    def _compute_hash(self, data: dict) -> str:
        """Compute SHA-256 hash of JSON data for change detection."""
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

    def _check_already_loaded(self, file_type: str, new_hash: str) -> bool:
        """Check if this exact file was already loaded today."""
        existing = RbcmLoadHistory.query.filter_by(
            rblh_date=self.today,
            rblh_file_type=file_type,
            rblh_hash=new_hash,
            rblh_status='success'
        ).first()
        return existing is not None

    def _extract_categories(self, products: list) -> int:
        """Extract unique categories from products and upsert to rbcm_categories."""
        categories = {}
        for p in products:
            cat_id = p.get('idCategory')
            cat_name = p.get('categoryName')
            if cat_id and cat_name:
                categories[cat_id] = cat_name

        for cat_id, cat_name in categories.items():
            existing = RbcmCategory.query.get(cat_id)
            if existing:
                existing.rbcat_name = cat_name
            else:
                db.session.add(RbcmCategory(rbcat_id=cat_id, rbcat_name=cat_name))

        db.session.flush()
        return len(categories)

    def _extract_expansions(self, products: list) -> int:
        """Extract unique expansions from products and upsert to rbcm_expansions."""
        expansions = set()
        for p in products:
            exp_id = p.get('idExpansion')
            if exp_id:
                expansions.add(exp_id)

        for exp_id in expansions:
            existing = RbcmExpansion.query.get(exp_id)
            if not existing:
                db.session.add(RbcmExpansion(rbexp_id=exp_id))

        db.session.flush()
        return len(expansions)

    def _load_products(self, products: list, product_type: str) -> int:
        """Load products to rbcm_products. Upsert by date + idProduct."""
        count = 0
        for p in products:
            id_product = p.get('idProduct')
            if not id_product:
                continue

            existing = RbcmProduct.query.filter_by(
                rbprd_date=self.today,
                rbprd_id_product=id_product
            ).first()

            if existing:
                existing.rbprd_name = p.get('name', '')
                existing.rbprd_id_category = p.get('idCategory')
                existing.rbprd_category_name = p.get('categoryName')
                existing.rbprd_id_expansion = p.get('idExpansion')
                existing.rbprd_id_metacard = p.get('idMetacard')
                existing.rbprd_date_added = p.get('dateAdded')
                existing.rbprd_type = product_type
            else:
                db.session.add(RbcmProduct(
                    rbprd_date=self.today,
                    rbprd_id_product=id_product,
                    rbprd_name=p.get('name', ''),
                    rbprd_id_category=p.get('idCategory'),
                    rbprd_category_name=p.get('categoryName'),
                    rbprd_id_expansion=p.get('idExpansion'),
                    rbprd_id_metacard=p.get('idMetacard'),
                    rbprd_date_added=p.get('dateAdded'),
                    rbprd_type=product_type,
                ))
            count += 1

        db.session.flush()
        return count

    def _load_prices(self, price_guides: list) -> int:
        """Load price guide to rbcm_price. Insert new date rows."""
        count = 0
        for p in price_guides:
            id_product = p.get('idProduct')
            if not id_product:
                continue

            existing = RbcmPrice.query.filter_by(
                rbprc_date=self.today,
                rbprc_id_product=id_product
            ).first()

            if existing:
                existing.rbprc_id_category = p.get('idCategory')
                existing.rbprc_avg = p.get('avg')
                existing.rbprc_low = p.get('low')
                existing.rbprc_trend = p.get('trend')
                existing.rbprc_avg1 = p.get('avg1')
                existing.rbprc_avg7 = p.get('avg7')
                existing.rbprc_avg30 = p.get('avg30')
                existing.rbprc_avg_foil = p.get('avg-foil')
                existing.rbprc_low_foil = p.get('low-foil')
                existing.rbprc_trend_foil = p.get('trend-foil')
                existing.rbprc_avg1_foil = p.get('avg1-foil')
                existing.rbprc_avg7_foil = p.get('avg7-foil')
                existing.rbprc_avg30_foil = p.get('avg30-foil')
                existing.rbprc_low_ex = p.get('low-ex+')
            else:
                db.session.add(RbcmPrice(
                    rbprc_date=self.today,
                    rbprc_id_product=id_product,
                    rbprc_id_category=p.get('idCategory'),
                    rbprc_avg=p.get('avg'),
                    rbprc_low=p.get('low'),
                    rbprc_trend=p.get('trend'),
                    rbprc_avg1=p.get('avg1'),
                    rbprc_avg7=p.get('avg7'),
                    rbprc_avg30=p.get('avg30'),
                    rbprc_avg_foil=p.get('avg-foil'),
                    rbprc_low_foil=p.get('low-foil'),
                    rbprc_trend_foil=p.get('trend-foil'),
                    rbprc_avg1_foil=p.get('avg1-foil'),
                    rbprc_avg7_foil=p.get('avg7-foil'),
                    rbprc_avg30_foil=p.get('avg30-foil'),
                    rbprc_low_ex=p.get('low-ex+'),
                ))
            count += 1

        db.session.flush()
        return count

    def _update_product_card_map(self) -> dict:
        """Auto-map Cardmarket products to internal rbcards by name matching.

        Returns dict with counts: auto_matched, unmatched, already_mapped
        """
        from app.models.card import RbCard

        counts = {'auto_matched': 0, 'unmatched': 0, 'already_mapped': 0}

        # Get latest products (use today or most recent date)
        products = RbcmProduct.query.filter_by(rbprd_date=self.today).all()
        if not products:
            # Fallback: get most recent date
            latest = db.session.query(db.func.max(RbcmProduct.rbprd_date)).scalar()
            if latest:
                products = RbcmProduct.query.filter_by(rbprd_date=latest).all()

        for product in products:
            # Check if already mapped
            existing = RbcmProductCardMap.query.filter_by(
                rbpcm_id_product=product.rbprd_id_product
            ).first()

            if existing:
                counts['already_mapped'] += 1
                continue

            # Try exact name match (case-insensitive)
            matches = RbCard.query.filter(
                db.func.lower(RbCard.rbcar_name) == product.rbprd_name.lower()
            ).all()

            if len(matches) == 1:
                # Single match → auto-map
                db.session.add(RbcmProductCardMap(
                    rbpcm_id_product=product.rbprd_id_product,
                    rbpcm_rbset_id=matches[0].rbcar_rbset_id,
                    rbpcm_rbcar_id=matches[0].rbcar_id,
                    rbpcm_match_type='auto',
                    rbpcm_confidence=1.0,
                ))
                counts['auto_matched'] += 1
            else:
                counts['unmatched'] += 1

        db.session.flush()
        return counts

    def _record_history(self, file_type: str, hash_val: str, rows: int,
                        status: str, message: str):
        """Record load operation in rbcm_load_history."""
        db.session.add(RbcmLoadHistory(
            rblh_date=self.today,
            rblh_file_type=file_type,
            rblh_hash=hash_val,
            rblh_rows=rows,
            rblh_status=status,
            rblh_message=message,
            rblh_loaded_at=datetime.utcnow(),
        ))
        db.session.flush()

    def _add_step(self, step: str, status: str, message: str):
        """Add a new step to the progress tracker."""
        self.steps.append({'step': step, 'status': status, 'message': message})

    def _update_step(self, step: str, status: str, message: str):
        """Update the last step matching the given name."""
        for s in reversed(self.steps):
            if s['step'] == step:
                s['status'] = status
                s['message'] = message
                break

    def _result(self, success: bool) -> dict:
        """Build result dict."""
        return {
            'success': success,
            'date': self.today,
            'steps': self.steps,
            'errors': self.errors,
            'unmatched_count': self.unmatched_count,
        }
