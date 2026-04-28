"""
TDD tests for:
  - REQ-2: Taken slots are excluded from _expand_slots
  - REQ-3: Showcase rarity IS auto-matchable (generates 1 slot, rank 2.5)
  - REQ-4: Cards with suffix 's' (signed) ARE auto-matchable (rank 2.55+)
  - REQ-2b: Taken slots filtered by `taken` set
  - REQ-5: Legend matching uses {tags}, {name} composite keys
  - REQ-6: Auto-match prevents duplicate mappings
  - REQ-7 (integration): Teemo Scout scenario with missing promo card
  - REQ-8: Aphelios Showcase scenario (Showcase + signed get slots)

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
# Group G - Price signal priority
# ---------------------------------------------------------------------------

class TestPriceSignalPriority:

    def test_prefers_low_before_avg7_within_same_set(self, app, setup_sets, common_card):
        """The matcher must sort by low before avg7 when both are present."""
        from app.services.cardmarket_matcher import auto_match

        with app.app_context():
            exp = RbcmExpansion(rbexp_id=400, rbexp_name='Origins Low First', rbexp_rbset_id='OGN')
            db.session.add(exp)

            prod_low = RbcmProduct(
                rbprd_date='20260428',
                rbprd_id_product=4001,
                rbprd_name='Blade Strike',
                rbprd_id_metacard=4000,
                rbprd_id_expansion=400,
                rbprd_type='single',
            )
            prod_avg = RbcmProduct(
                rbprd_date='20260428',
                rbprd_id_product=4002,
                rbprd_name='Blade Strike',
                rbprd_id_metacard=4000,
                rbprd_id_expansion=400,
                rbprd_type='single',
            )
            db.session.add_all([prod_low, prod_avg])

            db.session.add_all([
                RbcmPrice(
                    rbprc_id_product=4001,
                    rbprc_date='20260428',
                    rbprc_low=1.00,
                    rbprc_avg7=9.00,
                ),
                RbcmPrice(
                    rbprc_id_product=4002,
                    rbprc_date='20260428',
                    rbprc_low=2.00,
                    rbprc_avg7=3.00,
                ),
            ])
            db.session.commit()

            result = auto_match(dry_run=False)

            foil_n = RbcmProductCardMap.query.filter_by(
                rbpcm_rbset_id='OGN',
                rbpcm_rbcar_id='01',
                rbpcm_foil='N',
            ).first()
            foil_s = RbcmProductCardMap.query.filter_by(
                rbpcm_rbset_id='OGN',
                rbpcm_rbcar_id='01',
                rbpcm_foil='S',
            ).first()

        assert result['success'] is True
        assert foil_n is not None
        assert foil_s is not None
        assert foil_n.rbpcm_id_product == 4001
        assert foil_s.rbpcm_id_product == 4002


# ---------------------------------------------------------------------------
# Group B - Slot exclusions (REQ-3, REQ-4)
# ---------------------------------------------------------------------------

class TestSlotExclusion:

    def test_showcase_rarity_generates_slot(self, app, setup_sets):
        """Cards with rarity='Showcase' must generate a slot (rank 2.5, between epic and unknown)."""
        from app.services.cardmarket_matcher import _expand_slots
        with app.app_context():
            card = RbCard(
                rbcar_rbset_id='OGN',
                rbcar_id='50',
                rbcar_name='Aphelios, Exalted',
                rbcar_type='Champion Unit',
                rbcar_rarity='Showcase',
                rbcar_tags='Aphelios, Mount Targon',
            )
            slots = _expand_slots(card)
            assert len(slots) == 1, f"Expected 1 slot for Showcase card, got {len(slots)}: {slots}"
            card_out, foil = slots[0]
            assert card_out.rbcar_id == '50'
            assert foil is None  # Showcase is not common/uncommon, single slot with foil=None

    def test_signed_suffix_generates_slot(self, app, setup_sets):
        """Cards with rbcar_id matching ^\\d+s$ (signed showcase) must generate a slot."""
        from app.services.cardmarket_matcher import _expand_slots
        with app.app_context():
            card = RbCard(
                rbcar_rbset_id='OGN',
                rbcar_id='15s',
                rbcar_name='Teemo, Scout',
                rbcar_type='Champion Unit',
                rbcar_rarity='Showcase',
                rbcar_tags=None,
            )
            slots = _expand_slots(card)
            assert len(slots) == 1, f"Expected 1 slot for signed card OGN-15s, got {len(slots)}: {slots}"

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

    def test_partitions_base_and_promo_products_by_exact_set(self, app, setup_sets):
        """Base and promo products in the same metacard must not steal each other's slots."""
        from app.services.cardmarket_matcher import auto_match

        with app.app_context():
            promo_set = RbSet(rbset_id='OGNX', rbset_name='Origins Promo', rbset_ncard=20)
            db.session.add(promo_set)

            db.session.add_all([
                RbCard(
                    rbcar_rbset_id='OGN',
                    rbcar_id='15',
                    rbcar_name='Teemo, Scout',
                    rbcar_type='Legend',
                    rbcar_rarity='Rare',
                    rbcar_tags=None,
                ),
                RbCard(
                    rbcar_rbset_id='OGNX',
                    rbcar_id='15',
                    rbcar_name='Teemo, Scout',
                    rbcar_type='Legend',
                    rbcar_rarity='Rare',
                    rbcar_tags=None,
                ),
            ])

            db.session.add_all([
                RbcmExpansion(rbexp_id=201, rbexp_name='Origins Base Teemo', rbexp_rbset_id='OGN'),
                RbcmExpansion(rbexp_id=202, rbexp_name='Origins Promo Teemo', rbexp_rbset_id='OGNX'),
            ])

            db.session.add_all([
                RbcmProduct(
                    rbprd_date='20260428',
                    rbprd_id_product=2011,
                    rbprd_name='Teemo, Scout',
                    rbprd_id_metacard=9200,
                    rbprd_id_expansion=201,
                    rbprd_type='single',
                ),
                RbcmProduct(
                    rbprd_date='20260428',
                    rbprd_id_product=2021,
                    rbprd_name='Teemo, Scout',
                    rbprd_id_metacard=9200,
                    rbprd_id_expansion=202,
                    rbprd_type='single',
                ),
            ])

            db.session.add_all([
                RbcmPrice(rbprc_id_product=2011, rbprc_date='20260428', rbprc_low=5.00),
                RbcmPrice(rbprc_id_product=2021, rbprc_date='20260428', rbprc_low=1.00),
            ])
            db.session.commit()

            result = auto_match(dry_run=False)

            base_map = RbcmProductCardMap.query.filter_by(rbpcm_id_product=2011).first()
            promo_map = RbcmProductCardMap.query.filter_by(rbpcm_id_product=2021).first()

        assert result['success'] is True
        assert result['assigned'] == 2
        assert base_map is not None
        assert promo_map is not None
        assert base_map.rbpcm_rbset_id == 'OGN'
        assert promo_map.rbpcm_rbset_id == 'OGNX'

    def test_teemo_base_and_promo_alts_do_not_cross_steal_slots(self, app, setup_sets):
        """Teemo variants must stay inside their resolved internal set partition."""
        from app.services.cardmarket_matcher import auto_match

        with app.app_context():
            promo_set = RbSet(rbset_id='OGNX', rbset_name='Origins Promo', rbset_ncard=20)
            db.session.add(promo_set)

            db.session.add_all([
                RbCard(
                    rbcar_rbset_id='OGN',
                    rbcar_id='15',
                    rbcar_name='Teemo, Scout',
                    rbcar_type='Legend',
                    rbcar_rarity='Rare',
                    rbcar_tags=None,
                ),
                RbCard(
                    rbcar_rbset_id='OGN',
                    rbcar_id='15a',
                    rbcar_name='Teemo, Scout',
                    rbcar_type='Legend',
                    rbcar_rarity='Rare',
                    rbcar_tags=None,
                ),
                RbCard(
                    rbcar_rbset_id='OGNX',
                    rbcar_id='15',
                    rbcar_name='Teemo, Scout',
                    rbcar_type='Legend',
                    rbcar_rarity='Rare',
                    rbcar_tags=None,
                ),
                RbCard(
                    rbcar_rbset_id='OGNX',
                    rbcar_id='15a',
                    rbcar_name='Teemo, Scout',
                    rbcar_type='Legend',
                    rbcar_rarity='Rare',
                    rbcar_tags=None,
                ),
            ])

            db.session.add_all([
                RbcmExpansion(rbexp_id=301, rbexp_name='Origins Base Teemo', rbexp_rbset_id='OGN'),
                RbcmExpansion(rbexp_id=302, rbexp_name='Origins Promo Teemo', rbexp_rbset_id='OGNX'),
            ])

            products = [
                (3011, 301, 4.00),
                (3012, 301, 6.00),
                (3021, 302, 1.00),
                (3022, 302, 2.00),
            ]
            for product_id, expansion_id, low_price in products:
                db.session.add(RbcmProduct(
                    rbprd_date='20260428',
                    rbprd_id_product=product_id,
                    rbprd_name='Teemo, Scout',
                    rbprd_id_metacard=9300,
                    rbprd_id_expansion=expansion_id,
                    rbprd_type='single',
                ))
                db.session.add(RbcmPrice(
                    rbprc_id_product=product_id,
                    rbprc_date='20260428',
                    rbprc_low=low_price,
                ))
            db.session.commit()

            result = auto_match(dry_run=False)

            base_maps = {
                row.rbpcm_id_product: row.rbpcm_rbcar_id
                for row in RbcmProductCardMap.query.filter(
                    RbcmProductCardMap.rbpcm_id_product.in_([3011, 3012])
                ).all()
            }
            promo_maps = {
                row.rbpcm_id_product: row.rbpcm_rbcar_id
                for row in RbcmProductCardMap.query.filter(
                    RbcmProductCardMap.rbpcm_id_product.in_([3021, 3022])
                ).all()
            }

        assert result['success'] is True
        assert result['assigned'] == 4
        assert base_maps == {3011: '15', 3012: '15a'}
        assert promo_maps == {3021: '15', 3022: '15a'}


# ---------------------------------------------------------------------------
# Group H - Aphelios Showcase scenario (REQ-8)
# ---------------------------------------------------------------------------

class TestApheliosShowcase:

    def test_showcase_and_signed_get_slots_in_aphelios(self, app, setup_sets):
        """Aphelios SFD: rare base, showcase, and showcase signed all get slots.
        Products sorted by low price: 0.02 -> rare, 29 -> showcase, 150 -> signed.
        """
        from app.services.cardmarket_matcher import auto_match

        with app.app_context():
            sfd = RbSet(rbset_id='SFD', rbset_name='Spiritforged', rbset_ncard=250)
            db.session.add(sfd)

            # 3 cards: rare, showcase, showcase signed
            db.session.add_all([
                RbCard(
                    rbcar_rbset_id='SFD', rbcar_id='49',
                    rbcar_name='Aphelios, Exalted', rbcar_type='Champion Unit',
                    rbcar_rarity='Rare', rbcar_tags='Aphelios, Mount Targon',
                ),
                RbCard(
                    rbcar_rbset_id='SFD', rbcar_id='224',
                    rbcar_name='Aphelios, Exalted', rbcar_type='Champion Unit',
                    rbcar_rarity='Showcase', rbcar_tags='Aphelios, Mount Targon',
                ),
                RbCard(
                    rbcar_rbset_id='SFD', rbcar_id='224s',
                    rbcar_name='Aphelios, Exalted', rbcar_type='Champion Unit',
                    rbcar_rarity='Showcase', rbcar_tags='Aphelios, Mount Targon',
                ),
            ])

            exp = RbcmExpansion(rbexp_id=6399, rbexp_name='Spiritforged', rbexp_rbset_id='SFD')
            db.session.add(exp)

            # 3 products for same metacard
            db.session.add_all([
                RbcmProduct(
                    rbprd_date='20260428', rbprd_id_product=866775,
                    rbprd_name='Aphelios, Exalted', rbprd_id_metacard=458346,
                    rbprd_id_expansion=6399, rbprd_type='single',
                ),
                RbcmProduct(
                    rbprd_date='20260428', rbprd_id_product=866971,
                    rbprd_name='Aphelios, Exalted', rbprd_id_metacard=458346,
                    rbprd_id_expansion=6399, rbprd_type='single',
                ),
                RbcmProduct(
                    rbprd_date='20260428', rbprd_id_product=867003,
                    rbprd_name='Aphelios, Exalted', rbprd_id_metacard=458346,
                    rbprd_id_expansion=6399, rbprd_type='single',
                ),
            ])

            db.session.add_all([
                RbcmPrice(rbprc_id_product=866775, rbprc_date='20260428', rbprc_low=0.02, rbprc_avg7_foil=0.2),
                RbcmPrice(rbprc_id_product=866971, rbprc_date='20260428', rbprc_low=29.0, rbprc_avg7_foil=48.04),
                RbcmPrice(rbprc_id_product=867003, rbprc_date='20260428', rbprc_low=150.0, rbprc_avg7_foil=295.43),
            ])
            db.session.commit()

            result = auto_match(dry_run=False)

        assert result['success'] is True
        # 3 products, 3 slots (rare, showcase, showcase-signed) => all 3 assigned
        assert result['assigned'] == 3, f"Expected 3 assigned, got {result['assigned']}. Result: {result}"

    def test_showcase_rank_between_epic_and_unknown(self, app, setup_sets):
        """Showcase rank must be 2.5 (between epic=2 and unknown=3)."""
        from app.services.cardmarket_matcher import card_rank_key

        rare_card = RbCard(rbcar_rbset_id='SFD', rbcar_id='49', rbcar_rarity='Rare',
                           rbcar_name='Test', rbcar_type='Unit', rbcar_tags=None)
        epic_card = RbCard(rbcar_rbset_id='SFD', rbcar_id='50', rbcar_rarity='Epic',
                           rbcar_name='Test', rbcar_type='Unit', rbcar_tags=None)
        showcase_card = RbCard(rbcar_rbset_id='SFD', rbcar_id='224', rbcar_rarity='Showcase',
                               rbcar_name='Test', rbcar_type='Unit', rbcar_tags=None)

        rare_key = card_rank_key(rare_card)
        epic_key = card_rank_key(epic_card)
        showcase_key = card_rank_key(showcase_card)

        assert rare_key < epic_key < showcase_key, (
            f"Expected rare < epic < showcase, got rare={rare_key}, epic={epic_key}, showcase={showcase_key}"
        )
