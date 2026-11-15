"""RESET-b S1, S2 (AC1): every table of the metadata is classified for the production data reset.

A unit that adds a table must classify it in `app/services/data_reset.py::TABLE_POLICY`
(AGENTS.md "Adding a New Model"); this test names the table it forgot.
"""
from app import db
from app.services import data_reset
from app.services.data_reset import KEEP, SPECIAL, TABLE_POLICY, WIPE


def metadata_names():
    return {t.name for t in db.metadata.sorted_tables if t.schema == 'riftbound'}


def test_every_metadata_table_is_classified_and_no_key_is_stale(app):
    problem = data_reset.policy_problems(metadata_names())
    assert problem is None, problem
    assert set(TABLE_POLICY) == metadata_names()


def test_the_problem_names_a_missing_and_a_stale_table(app):
    names = (metadata_names() - {'rbcardbans'}) | {'rboauthlinks'}
    policy = dict(TABLE_POLICY)
    assert data_reset.policy_problems(names, policy) == (
        'Unclassified tables: rboauthlinks; stale TABLE_POLICY keys: rbcardbans')
    assert data_reset.policy_problems(names - {'rboauthlinks'}, policy) == (
        'Stale TABLE_POLICY keys: rbcardbans')


def test_values_are_keep_wipe_or_special_only():
    assert set(TABLE_POLICY.values()) == {KEEP, WIPE, SPECIAL}


def test_the_special_tables_are_users_jobs_and_expansions():
    assert {t for t, c in TABLE_POLICY.items() if c == SPECIAL} == {
        'rbusers', 'rbjobs', 'rbcm_expansions'}


def test_the_owner_decisions_of_2026_11_12():
    keep = {t for t, c in TABLE_POLICY.items() if c == KEEP}
    assert keep == {'rbcm_price', 'rbcm_products', 'rbcm_load_history', 'rbcm_categories',
                    'rbcm_ignored', 'rbproducts', 'rbcardbans'}
    for table in ('rbset', 'rbcards', 'rbcm_product_card_map', 'rbadminaudit', 'rbusermfa',
                  'rbrecoverycodes', 'rbcardmarket', 'rbsessions', 'rbapikeys'):
        assert TABLE_POLICY[table] == WIPE, table
    assert 'alembic_version' not in TABLE_POLICY
    assert len(TABLE_POLICY) == 35
    assert sum(c == WIPE for c in TABLE_POLICY.values()) == 25
