"""
TDD tests for:
  - REQ-2: Taken slots are excluded from _expand_slots
  - REQ-3: Showcase rarity never auto-matches
  - REQ-4: Cards with suffix 's' never auto-match
  - REQ-5: Legend matching uses {tags}, {name} composite keys
  - REQ-6: Auto-match prevents duplicate mappings
  - REQ-7 (integration): Teemo Scout scenario with missing promo card

Tests written FIRST (RED), then implementation.
"""
import pytest
from unittest.mock import patch
from app import db
from app.models import RbSet, RbCard
from app.models.cardmarket import (
    RbcmProduct, RbcmPrice, RbcmExpansion, RbcmProductCardMap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def setup_sets(app):
    """Create base sets needed by most tests."""
    with app.app_context():
        s = RbSet(rbset_id='OGN', rbset_name='Origins', rbset_ncard=100)
        db.session.add(s)
        db.session.commit()


@pytest.fixture
def legend_card(app, setup_sets):
    """Create a Legend card: Ahri, tags='The Nine-Tailed Fox'."""
    with app.app_context():
        c = RbCard(
            rbcar_rbset_id='OGN',
            rbcar_id='42',
            rbcar_name='Ahri',
            rbcar_type='Legend',
            rbcar_rarity='Rare',
            rbcar_tags='The Nine-Tailed Fox',
        )
        db.session.add(c)
        db.session.commit()


@pytest.fixture
def common_card(app, setup_sets):
    """Create a Common (non-legend) card."""
    with app.app_context():
        c = RbCard(
            rbcar_rbset_id='OGN',
            rbcar_id='01',
            rbcar_name='Blade Strike',
            rbcar_type='Spell',
            rbcar_rarity='Common',
            rbcar_tags=None,
        )
        db.session.add(c)
        db.session.commit()


# ---------------------------------------------------------------------------
# Group E - Legend index tests
# ---------------------------------------------------------------------------

class TestLegendIndex:

    def test_legend_indexed_by_tags_plus_name(self, app, legend_card):
        """Legend card must appear in index under normalize_name('{tags}, {name}')."""
        from app.services.cardmarket_matcher import _build_card_index, normalize_name
        with app.app_context():
            idx = _build_card_index()
            key = normalize_name('The Nine-Tailed Fox, Ahri')
            assert key in idx, f"Key '{key}' not found in index. Keys: {list(idx.keys())[:10]}"
            cards = idx[key]
            assert len(cards) >= 1
            assert cards[0].rbcar_name == 'Ahri'

    def test_legend_indexed_by_name_plus_tags(self, app, legend_card):
        """Legend card must appear in index under normalize_name('{name}, {tags}')."""
        from app.services.cardmarket_matcher import _build_card_index, normalize_name
        with app.app_context():
            idx = _build_card_index()
            key = normalize_name('Ahri, The Nine-Tailed Fox')
            assert key in idx, f"Key '{key}' not found in index. Keys: {list(idx.keys())[:10]}"
            cards = idx[key]
            assert len(cards) >= 1
            assert cards[0].rbcar_name == 'Ahri'

    def test_non_legend_indexed_by_name_only(self, app, common_card):
        """Non-legend card must NOT have composite keys — only indexed by name."""
        from app.services.cardmarket_matcher import _build_card_index, normalize_name
        with app.app_context():
            idx = _build_card_index()
            name_key = normalize_name('Blade Strike')
            assert name_key in idx
            # No extra composite keys should exist for a non-legend
            all_keys = list(idx.keys())
            composite_keys = [k for k in all_keys if 'blade' in k and ',' in k.replace(' ', '')]
            assert len(composite_keys) == 0, f"Unexpected composite keys for non-legend: {composite_keys}"


# ---------------------------------------------------------------------------
# Group F - Duplicate mapping guard tests
# ---------------------------------------------------------------------------

class TestDuplicateMappingGuard:

    def _setup_products_and_mapping(self, app):
        """Seed: expansion, product A (already mapped), product B (unmapped)."""
        with app.app_context():
            exp = RbcmExpansion(rbexp_id=100, rbexp_name='Origins Exp', rbexp_rbset_id='OGN')
            db.session.add(exp)

            prod_a = RbcmProduct(
                rbprd_date='20260101',
                rbprd_id_product=1001,
                rbprd_name='Blade Strike',
                rbprd_id_metacard=500,
                rbprd_id_expansion=100,
                rbprd_type='single',
            )
            prod_b = RbcmProduct(
                rbprd_date='20260101',
                rbprd_id_product=1002,
                rbprd_name='Blade Strike',
                rbprd_id_metacard=500,
                rbprd_id_expansion=100,
                rbprd_type='single',
            )
            db.session.add_all([prod_a, prod_b])

            # product_a is already mapped to OGN/01/N (simulate a manual or prior auto-match)
            existing = RbcmProductCardMap(
                rbpcm_id_product=1001,
                rbpcm_rbset_id='OGN',
                rbpcm_rbcar_id='01',
                rbpcm_foil='N',
                rbpcm_match_type='manual',
            )
            db.session.add(existing)
            db.session.commit()

    def test_match_skips_when_target_already_mapped(self, app, common_card):
        """When target (set, card, foil) already has a DIFFERENT idProduct mapped,
        auto_match must NOT assign the new product to that slot.

        With REQ-2 pre-filter: the taken slot is excluded from _expand_slots
        before pairing, so product_b becomes unmatched (not review).
        The review counter is reserved for race-condition conflicts caught at INSERT.
        """
        self._setup_products_and_mapping(app)

        from app.services.cardmarket_matcher import auto_match
        with app.app_context():
            result = auto_match(dry_run=False)

        # product_b (1002): slot (OGN, 01, N) is taken by product_a (1001).
        # REQ-2: taken-slot pre-filter removes the N slot.
        # But (OGN, 01, S) is free → product_b gets assigned to the S (foil) slot.
        # The key guarantee: product_b does NOT overwrite product_a's (OGN, 01, N) mapping.
        assert result['success'] is True
        assert result['review'] == 0    # no conflict — different slot used
        # Verify no mapping was written to the N slot for product_b
        with app.app_context():
            from app.models.cardmarket import RbcmProductCardMap
            n_slot_map = RbcmProductCardMap.query.filter_by(
                rbpcm_rbset_id='OGN',
                rbpcm_rbcar_id='01',
                rbpcm_foil='N',
            ).first()
            # The N slot must still belong to product_a (1001), not product_b (1002)
            assert n_slot_map is not None
            assert n_slot_map.rbpcm_id_product == 1001

    def test_match_allows_different_foil_for_same_card(self, app, common_card):
        """The duplicate guard is keyed on (set, card, foil).

        A mapping for (OGN, 01, N) must NOT prevent a mapping for (OGN, 01, S).
        We verify this by confirming: when no conflict on the S slot, the product
        is assigned and review stays at 0.
        """
        from app.services.cardmarket_matcher import RbcmProductCardMap, auto_match
        from app.services.cardmarket_matcher import _build_card_index, normalize_name

        with app.app_context():
            exp = RbcmExpansion(rbexp_id=300, rbexp_name='Origins Exp 3', rbexp_rbset_id='OGN')
            db.session.add(exp)

            # One unmapped product in metacard group 700 (will be matched to OGN/01/N slot)
            prod = RbcmProduct(
                rbprd_date='20260101',
                rbprd_id_product=3001,
                rbprd_name='Blade Strike',
                rbprd_id_metacard=700,
                rbprd_id_expansion=300,
                rbprd_type='single',
            )
            db.session.add(prod)
            db.session.commit()

        from app.services.cardmarket_matcher import auto_match
        with app.app_context():
            result = auto_match(dry_run=False)

        # No existing mapping for (OGN, 01, N), so product 3001 should be assigned
        # and review should NOT increment
        assert result['success'] is True
        assert result['assigned'] >= 1
        assert result['review'] == 0

    def test_response_has_review_counter(self, app):
        """auto_match response must always include a 'review' key."""
        from app.services.cardmarket_matcher import auto_match
        with app.app_context():
            result = auto_match(dry_run=True)
        assert 'review' in result


# ---------------------------------------------------------------------------
# Group B - Slot exclusions (REQ-3, REQ-4)
# ---------------------------------------------------------------------------

class TestSlotExclusion:

    def test_excludes_showcase_rarity(self, app, setup_sets):
        """Cards with rarity='Showcase' must generate zero slots."""
        from app.services.cardmarket_matcher import _expand_slots
        with app.app_context():
            card = RbCard(
                rbcar_rbset_id='OGN',
                rbcar_id='50',
                rbcar_name='Teemo, Scout',
                rbcar_type='Legend',
                rbcar_rarity='Showcase',
                rbcar_tags=None,
            )
            slots = _expand_slots(card)
            assert slots == [], f"Expected [] for Showcase card, got {slots}"

    def test_excludes_signed_suffix(self, app, setup_sets):
        """Cards with rbcar_id matching ^\\d+s$ must generate zero slots."""
        from app.services.cardmarket_matcher import _expand_slots
        with app.app_context():
            card = RbCard(
                rbcar_rbset_id='OGN',
                rbcar_id='15s',
                rbcar_name='Teemo, Scout',
                rbcar_type='Legend',
                rbcar_rarity='Rare',
                rbcar_tags=None,
            )
            slots = _expand_slots(card)
            assert slots == [], f"Expected [] for signed card OGN-15s, got {slots}"

    def test_excludes_taken_slot(self, app, setup_sets):
        """When slot (rbset_id, rbcar_id, foil) is in `taken`, _expand_slots returns []."""
        from app.services.cardmarket_matcher import _expand_slots
        with app.app_context():
            card = RbCard(
                rbcar_rbset_id='OGN',
                rbcar_id='15',
                rbcar_name='Teemo, Scout',
                rbcar_type='Legend',
                rbcar_rarity='Rare',
                rbcar_tags=None,
            )
            taken = {('OGN', '15', None)}
            slots = _expand_slots(card, taken=taken)
            assert slots == [], f"Expected [] when slot is taken, got {slots}"


# ---------------------------------------------------------------------------
# Group D - Teemo Scout integration scenario (REQ-5)
# ---------------------------------------------------------------------------

class TestTeemoScenario:

    def test_teemo_scout_no_promo(self, app, setup_sets):
        """Integration: 2 rare cards (base + alt), 5 products. Only 2 slots exist.
        Expected: assigned=2, unmatched=3.
        """
        from app.services.cardmarket_matcher import auto_match
        import datetime

        with app.app_context():
            # Two cards: OGN-15 (rare base), OGN-15a (rare alt)
            card_base = RbCard(
                rbcar_rbset_id='OGN',
                rbcar_id='15',
                rbcar_name='Teemo, Scout',
                rbcar_type='Legend',
                rbcar_rarity='Rare',
                rbcar_tags=None,
            )
            card_alt = RbCard(
                rbcar_rbset_id='OGN',
                rbcar_id='15a',
                rbcar_name='Teemo, Scout',
                rbcar_type='Legend',
                rbcar_rarity='Rare',
                rbcar_tags=None,
            )
            db.session.add_all([card_base, card_alt])

            # Expansion mapped to OGN
            exp = RbcmExpansion(rbexp_id=200, rbexp_name='Origins Teemo', rbexp_rbset_id='OGN')
            db.session.add(exp)

            today = '20260426'
            metacard_id = 9001

            # 5 products sharing the same metacard
            prices_eur = [0.03, 0.99, 1.48, 5.0, 10.0]
            products = []
            for i, price in enumerate(prices_eur, start=1):
                p = RbcmProduct(
                    rbprd_date=today,
                    rbprd_id_product=9000 + i,
                    rbprd_name='Teemo, Scout',
                    rbprd_id_metacard=metacard_id,
                    rbprd_id_expansion=200,
                    rbprd_type='single',
                )
                products.append(p)
                pr = RbcmPrice(
                    rbprc_id_product=9000 + i,
                    rbprc_date=today,
                    rbprc_avg7=price,
                )
                db.session.add(pr)
            db.session.add_all(products)
            db.session.commit()

        with app.app_context():
            result = auto_match(dry_run=False)

        assert result['success'] is True, f"auto_match failed: {result}"
        assert result['assigned'] == 2, (
            f"Expected assigned=2 (base + alt), got {result['assigned']}. "
            f"Full result: {result}"
        )
        assert result['unmatched'] == 3, (
            f"Expected unmatched=3 (promo missing + 2 specials), got {result['unmatched']}. "
            f"Full result: {result}"
        )
