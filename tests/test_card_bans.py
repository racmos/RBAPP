"""F2-a S2/S5/S6: the ban service `app/services/bans.py` (normalization, reads,
add/remove), through its public functions and the rows they leave."""
import pytest

from app.services.bans import name_key


# --- S2 name_key ---------------------------------------------------------------------

def test_name_key_trims_casefolds_unifies_apostrophes_and_spaces():
    assert name_key("  Kai’Sa,   Daughter of the Void ") == "kai'sa, daughter of the void"


def test_name_key_ignores_case():
    assert name_key('JINX, Loose Cannon') == name_key('jinx, loose cannon')


@pytest.mark.parametrize('raw, key', [
    ('Kai‘Sa', "kai'sa"),                       # U+2018 too
    ("Kai'Sa", "kai'sa"),
    ('Straße', 'strasse'),                      # casefold, not lower
    ('\tTabs\nand  newlines ', 'tabs and newlines'),
    (' \t\n ', ''),
])
def test_name_key_rules(raw, key):
    assert name_key(raw) == key
