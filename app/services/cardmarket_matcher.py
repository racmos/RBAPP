"""
Cardmarket auto-matcher.

Asigna automáticamente cada idProduct sin mapear a la mejor combinación
(rbset_id, rbcar_id, rbpcm_foil) basándose en:

  - idMetacard (productos del mismo metacard son la "misma carta", distintas
    variantes / foils / promos).
  - El precio: para cartas del mismo metacard, el precio refleja la variante.
  - La rareza interna en rbcards y los sufijos del rbcar_id.

Reglas (consolidadas con el usuario):

  - common / uncommon de set NO promo: 2 productos -> bajo=normal, alto=foil.
    Si hay un 3º producto: el más caro mapea a la versión promo de esa misma
    carta, que vive en el set terminado en X (p.ej. OGN-1 -> OGNX-1).
  - rare / epic: NO tienen foil. Las distintas variantes son entradas
    SEPARADAS en rbcards con sufijos en rbcar_id (79, 79a) o en sets promo
    (OGN -> OGNX). Orden creciente de precio aproximado:

      rare base  <  rare promo  <  epic base  <  epic showcase signed  <  epic plated promo

    Esto se modela en `card_rank_key` mediante una clave numérica.

El algoritmo:

  1. Cargar productos sin mapear de la última fecha de carga.
  2. Cargar el último precio por producto (avg7 / avg7_foil / low) como
     señal ordenadora.
  3. Agrupar por idMetacard.
  4. Para cada grupo, normalizar el nombre y buscar candidatos en rbcards.
  5. Expandir cada candidato common/uncommon de set NO promo en dos "slots"
     (foil='N' y foil='S').
  6. Ordenar productos por precio asc y slots por rank_key asc, emparejar 1:1.
  7. Productos sobrantes quedan unmatched (revisión manual desde la UI).

El método `auto_match(dry_run=...)` devuelve un dict con stats y muestras.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from sqlalchemy import func

from app import db
from app.models import RbCard
from app.models.cardmarket import (
    RbcmProduct, RbcmPrice, RbcmExpansion, RbcmProductCardMap, RbcmIgnored,
)


# Palabras de "ruido" que aparecen en nombres de productos Cardmarket y que
# debemos eliminar para parear contra el nombre de la carta interna.
_NOISE_RE = re.compile(
    r'\b(foil|showcase|signed|plated|promo|extended|alt(?:ernate)?\s+art|'
    r'borderless|full[\s-]*art|prerelease|prelaunch|launch|'
    r'v\.?\s*\d+|version\s*\d+)\b',
    re.IGNORECASE,
)

_PUNCT_RE = re.compile(r'[^a-zA-Z0-9 ]+')
_WS_RE = re.compile(r'\s+')


def normalize_name(name: Optional[str]) -> str:
    """Normaliza un nombre para comparar: minúsculas, sin sufijos de variante,
    sin puntuación, sin números sueltos al final, espacios colapsados."""
    if not name:
        return ''
    n = _NOISE_RE.sub(' ', name)
    n = _PUNCT_RE.sub(' ', n)
    # Quita números sueltos (p.ej. "Card Name 247" -> "Card Name")
    n = re.sub(r'\b\d+[a-z]?\b', ' ', n)
    n = _WS_RE.sub(' ', n).strip().lower()
    return n


_RARITY_RANK = {'common': 0, 'uncommon': 0, 'rare': 1, 'epic': 2, 'showcase': 2.5}


def card_rank_key(card: RbCard):
    """Clave de orden creciente por "precio esperado".

    rare base < rare promo (X) < rare alt (suffix a) < epic base < showcase
        < showcase signed (suffix s) < epic plated promo (epic en X)
    """
    rarity = (card.rbcar_rarity or '').lower()
    rbset_id = card.rbcar_rbset_id or ''
    rbcar_id = card.rbcar_id or ''
    is_promo_set = rbset_id.endswith('X')

    suffix_match = re.match(r'^\d+([a-z]+)$', rbcar_id)
    suffix = suffix_match.group(1) if suffix_match else ''

    base = _RARITY_RANK.get(rarity, 3) * 1.0

    suffix_bonus = 0.0
    if 'a' in suffix:
        suffix_bonus += 0.30  # showcase v.2
    if 's' in suffix:
        suffix_bonus += 0.55  # showcase signed v.3

    set_bonus = 0.0
    if is_promo_set:
        if rarity == 'epic':
            set_bonus = 1.50  # plated promo (la más cara)
        elif rarity == 'rare':
            set_bonus = 0.20  # rare promo
        else:
            set_bonus = 0.10  # common/uncommon promo

    return (base + suffix_bonus + set_bonus, rbset_id, rbcar_id)


def _get_latest_prices() -> dict[int, float]:
    """Devuelve {id_product: precio_orden}. Usa low, low_foil, avg7,
    avg7_foil o 0 en ese orden. Sólo de la última fecha disponible por
    producto."""
    latest_per_prod = dict(
        db.session.query(
            RbcmPrice.rbprc_id_product,
            func.max(RbcmPrice.rbprc_date),
        ).group_by(RbcmPrice.rbprc_id_product).all()
    )
    if not latest_per_prod:
        return {}

    prices = {}
    rows = RbcmPrice.query.all()
    for p in rows:
        if latest_per_prod.get(p.rbprc_id_product) != p.rbprc_date:
            continue
        v = (
            p.rbprc_low
            or p.rbprc_low_foil
            or p.rbprc_avg7
            or p.rbprc_avg7_foil
            or 0
        )
        prices[p.rbprc_id_product] = float(v) if v is not None else 0.0
    return prices


def _get_partition_candidates(
    candidates: list[RbCard],
    partition_prods: list[RbcmProduct],
    exp_to_set: dict[int, str],
) -> list[RbCard]:
    """Resuelve candidatos para una partición de productos del mismo set.

    Si existen candidatos del set exacto, sólo se usan esos. Si no, cae al
    comportamiento previo: considerar el set base + su variante promo (X).
    """
    exact_sets = []
    seen_exact_sets = set()
    for prod in partition_prods:
        exact_set = exp_to_set.get(prod.rbprd_id_expansion or 0)
        if exact_set and exact_set not in seen_exact_sets:
            seen_exact_sets.add(exact_set)
            exact_sets.append(exact_set)

    exact_candidates = [
        c for c in candidates
        if c.rbcar_rbset_id in seen_exact_sets
    ]
    if exact_candidates:
        return exact_candidates

    related_sets = set()
    for sid in exact_sets:
        related_sets.add(sid)
        if sid.endswith('X'):
            related_sets.add(sid[:-1])
        else:
            related_sets.add(sid + 'X')

    if related_sets:
        preferred = [c for c in candidates if c.rbcar_rbset_id in related_sets]
        if preferred:
            return preferred

    return candidates


def _group_products_by_metacard(ignored: set | None = None):
    """Productos sin mapear, de la última fecha, agrupados por idMetacard.

    `ignored` is a set of (id_product, name) tuples to skip.
    Returns (groups_dict, skipped_no_metacard, ignored_count).
    """
    latest_date = db.session.query(func.max(RbcmProduct.rbprd_date)).scalar()
    if not latest_date:
        return {}, 0, 0

    mapped_ids = {r[0] for r in db.session.query(RbcmProductCardMap.rbpcm_id_product).all()}
    ignored = ignored or set()

    products = RbcmProduct.query.filter(
        RbcmProduct.rbprd_date == latest_date,
        RbcmProduct.rbprd_type == 'single',
    ).all()

    groups = defaultdict(list)
    skipped_no_metacard = 0
    ignored_count = 0
    for p in products:
        if p.rbprd_id_product in mapped_ids:
            continue
        if (p.rbprd_id_product, p.rbprd_name) in ignored:
            ignored_count += 1
            continue
        if not p.rbprd_id_metacard:
            skipped_no_metacard += 1
            continue
        groups[p.rbprd_id_metacard].append(p)
    return groups, skipped_no_metacard, ignored_count


def _build_card_index() -> dict[str, list[RbCard]]:
    """Indice nombre_normalizado -> [RbCard, ...].

    Para cartas de tipo Legend se añaden además entradas compuestas con los
    rbcar_tags, en ambos órdenes:
      - normalize_name(f"{tags}, {name}")  e.g. 'the nine tailed fox ahri'
      - normalize_name(f"{name}, {tags}")  e.g. 'ahri the nine tailed fox'

    Cardmarket usa ambas convenciones según la edición del producto, por lo
    que indexar ambas órdenes maximiza la cobertura del auto-matcher (REQ-5).
    """
    cards = RbCard.query.all()
    idx = defaultdict(list)
    for c in cards:
        idx[normalize_name(c.rbcar_name)].append(c)
        # REQ-5: Legend cards indexed by composite name
        if (c.rbcar_type or '').lower() == 'legend' and c.rbcar_tags:
            tags = c.rbcar_tags
            name = c.rbcar_name or ''
            idx[normalize_name(f"{tags}, {name}")].append(c)
            idx[normalize_name(f"{name}, {tags}")].append(c)
    return idx


def _expand_slots(
    card: RbCard,
    taken: Optional[set] = None,
) -> list[tuple[RbCard, Optional[str]]]:
    """Para cada candidato genera ranuras (card, foil).

    common/uncommon de set NO promo -> dos slots ('N' y 'S').
    Resto -> un único slot con foil=None.

    Showcase and signed (suffix 's') cards ARE matchable (rank 2.5+).
    REQ-2: Filter slots already present in `taken` set
           (set of (rbset_id, rbcar_id, foil) tuples from RbcmProductCardMap).
    """
    rarity = (card.rbcar_rarity or '').lower()
    rbcar_id = card.rbcar_id or ''

    is_promo_set = (card.rbcar_rbset_id or '').endswith('X')
    if rarity in ('common', 'uncommon') and not is_promo_set:
        # foil cuesta más, pero como ambos slots representan el MISMO rbcar,
        # van uno justo después del otro en el orden de productos asc por precio.
        raw_slots = [(card, 'N'), (card, 'S')]
    else:
        raw_slots = [(card, None)]

    # REQ-2: Remove slots already taken by existing mappings
    if taken is None:
        return raw_slots
    return [
        s for s in raw_slots
        if (card.rbcar_rbset_id, card.rbcar_id, s[1]) not in taken
    ]


def _get_expansion_to_set_map() -> dict[int, str]:
    return dict(
        db.session.query(
            RbcmExpansion.rbexp_id, RbcmExpansion.rbexp_rbset_id
        ).filter(RbcmExpansion.rbexp_rbset_id.isnot(None)).all()
    )


def auto_match(dry_run: bool = False, max_groups: Optional[int] = None) -> dict:
    """Ejecuta el auto-matcher. `dry_run=True` no escribe nada en BD.

    Devuelve dict con: assigned, unmatched, skipped, no_candidates, review,
    samples (lista de hasta 25 emparejamientos para revisión).

    El counter `review` acumula mappings skipped porque la combinación
    (rbset_id, rbcar_id, foil) ya existe en BD con un idProduct distinto
    (REQ-6: duplicate mapping guard).
    """
    # Load ignored set once: (id_product, name) tuples
    ignored: set[tuple] = {
        (r.rbig_id_product, r.rbig_name)
        for r in RbcmIgnored.query.all()
    }

    groups, skipped_no_metacard, ignored_count = _group_products_by_metacard(ignored=ignored)
    if not groups:
        return {
            'success': True,
            'assigned': 0,
            'unmatched': 0,
            'skipped': skipped_no_metacard,
            'no_candidates': 0,
            'review': 0,
            'ignored_count': ignored_count,
            'samples': [],
            'message': 'No hay productos pendientes de mapear',
        }

    prices = _get_latest_prices()
    cards_by_norm = _build_card_index()
    exp_to_set = _get_expansion_to_set_map()

    # REQ-2: Load existing taken slots once (avoids N+1 and blocks re-assignment)
    taken: set[tuple] = set(
        db.session.query(
            RbcmProductCardMap.rbpcm_rbset_id,
            RbcmProductCardMap.rbpcm_rbcar_id,
            RbcmProductCardMap.rbpcm_foil,
        ).all()
    )

    assigned = 0
    unmatched = 0
    no_candidates = 0
    review = 0  # REQ-6: duplicate mapping conflicts
    samples = []

    items = list(groups.items())
    if max_groups:
        items = items[:max_groups]

    for metacard_id, prods in items:
        # Nombre normalizado (todos los productos del metacard suelen compartir
        # el nombre base, pero por seguridad normalizamos varios)
        norm_candidates = {normalize_name(p.rbprd_name) for p in prods if p.rbprd_name}
        norm_candidates.discard('')
        candidates: list[RbCard] = []
        for n in norm_candidates:
            candidates.extend(cards_by_norm.get(n, []))
        # de-dup preservando orden
        seen = set()
        candidates = [c for c in candidates
                      if (c.rbcar_rbset_id, c.rbcar_id) not in seen
                      and not seen.add((c.rbcar_rbset_id, c.rbcar_id))]

        if not candidates:
            no_candidates += len(prods)
            continue

        partitions = defaultdict(list)
        for prod in prods:
            partitions[exp_to_set.get(prod.rbprd_id_expansion or 0)].append(prod)

        for partition_prods in partitions.values():
            partition_candidates = _get_partition_candidates(
                candidates=candidates,
                partition_prods=partition_prods,
                exp_to_set=exp_to_set,
            )

            # Generar slots ordenados por rank_key creciente
            partition_candidates.sort(key=card_rank_key)
            slots: list[tuple[RbCard, Optional[str]]] = []
            for c in partition_candidates:
                slots.extend(_expand_slots(c, taken=taken))

            # Productos ordenados por precio asc dentro de su partición
            prods_sorted = sorted(
                partition_prods,
                key=lambda p: (prices.get(p.rbprd_id_product, 0.0), p.rbprd_id_product),
            )

            # Emparejamiento 1:1
            for prod, slot in zip(prods_sorted, slots):
                card, foil = slot

                # REQ-6: Duplicate mapping guard — skip if (set, card, foil) already
                # mapped to a DIFFERENT idProduct (same idProduct = idempotent, OK).
                if not dry_run:
                    existing_map = RbcmProductCardMap.query.filter_by(
                        rbpcm_rbset_id=card.rbcar_rbset_id,
                        rbpcm_rbcar_id=card.rbcar_id,
                        rbpcm_foil=foil,
                    ).first()
                    if existing_map and existing_map.rbpcm_id_product != prod.rbprd_id_product:
                        review += 1
                        continue
                    if existing_map and existing_map.rbpcm_id_product == prod.rbprd_id_product:
                        # Idempotent re-run — already correctly mapped, skip silently
                        continue

                    m = RbcmProductCardMap(
                        rbpcm_id_product=prod.rbprd_id_product,
                        rbpcm_rbset_id=card.rbcar_rbset_id,
                        rbpcm_rbcar_id=card.rbcar_id,
                        rbpcm_foil=foil,
                        rbpcm_match_type='auto',
                        rbpcm_confidence=0.7,
                    )
                    db.session.add(m)
                assigned += 1
                samples.append({
                    'id_product': prod.rbprd_id_product,
                    'product_name': prod.rbprd_name,
                    'price': prices.get(prod.rbprd_id_product, 0.0),
                    'rbset_id': card.rbcar_rbset_id,
                    'rbcar_id': card.rbcar_id,
                    'rbcar_name': card.rbcar_name,
                    'rbpcm_foil': foil,
                    'rbcar_rarity': card.rbcar_rarity,
                })

            # Productos sobrantes (más productos que slots disponibles)
            extra = max(0, len(prods_sorted) - len(slots))
            unmatched += extra

    if not dry_run:
        db.session.commit()

    return {
        'success': True,
        'assigned': assigned,
        'unmatched': unmatched,
        'skipped': skipped_no_metacard,
        'no_candidates': no_candidates,
        'review': review,
        'ignored_count': ignored_count,
        'samples': samples,
    }
