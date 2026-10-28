"""Value domains of the interface preferences (PREF-2).

One definition for the three layers that must agree: the `PrefsUpdate` schema
(`validators.py`), the CHECK constraints of `RbUserPrefs`, and the tests.
`None` (SQL NULL) always means Auto and is allowed for every preference.
"""
LANGS = ('es', 'en')
DENSITIES = ('compact', 'regular', 'comfy')
ACCENTS = ('cyan', 'orange')
COLLECTION_VIEWS = ('table', 'grid')
BG_INTENSITY_MIN = 0
BG_INTENSITY_MAX = 100
PLAYSET_SIZE_MIN = 1
PLAYSET_SIZE_MAX = 9

# Preference key -> allowed values, for the text-valued ones.
CHOICES = {
    'lang': LANGS,
    'density': DENSITIES,
    'accent': ACCENTS,
    'collection_view': COLLECTION_VIEWS,
}

# Public key order (API payloads, service results).
PREF_KEYS = ('lang', 'density', 'accent', 'bg_intensity', 'collection_view', 'playset_size')


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """`column IN ('a', 'b')`: the CHECK text for a choice domain. Values are our own
    constants, never input, so quoting them inline is safe."""
    return f"{column} IN ({', '.join(repr(v) for v in values)})"
