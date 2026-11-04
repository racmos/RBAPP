import { useTranslation } from 'react-i18next';
import type { CollectionFacets, CollectionParams, GameMeta, StorageLocation } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { ChipGroup, FilterChip } from '@/components/ui/FilterChip';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { useEnumLabel } from '@/i18n';
import { sortSetsNewestFirst } from '@/lib/sets';
import { activeFilterCount } from './params';
import styles from './CollectionFilters.module.css';

type ListKey = 'set' | 'domain' | 'type' | 'rarity' | 'condition' | 'language' | 'location';

type CollectionFiltersProps = {
  params: CollectionParams;
  setParams: (patch: Partial<CollectionParams>) => void;
  meta: GameMeta | undefined;
  facets: CollectionFacets;
  total: number;
  onClear: () => void;
  /** The user's storage locations in their order (F16); no group when there are none. */
  locations?: StorageLocation[];
  /** The sheet's "show" button; a sidebar has none. */
  onClose?: () => void;
  variant?: 'sheet' | 'sidebar';
};

/**
 * The body of the filter sheet (F3-g S4): chips with group counts and three tri-states, each
 * with a visible label saying what it filters (owner feedback S24).
 */
export function CollectionFilters({
  params,
  setParams,
  meta,
  facets,
  total,
  onClear,
  locations = [],
  onClose,
  variant = 'sheet',
}: CollectionFiltersProps) {
  const { t } = useTranslation('collection');
  const { label } = useEnumLabel();

  const toggle = (key: ListKey, value: string) => {
    const current = params[key] ?? [];
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    setParams({ [key]: next.length > 0 ? next : undefined });
  };

  const chips = (
    key: ListKey,
    legend: string,
    values: string[],
    text: (value: string) => string,
    counts?: Record<string, number>,
  ) => (
    <ChipGroup legend={legend}>
      {values.map((value) => (
        <FilterChip
          key={value}
          label={text(value)}
          count={counts?.[value]}
          pressed={params[key]?.includes(value) ?? false}
          onClick={() => toggle(key, value)}
        />
      ))}
    </ChipGroup>
  );

  const tri = (key: 'selling' | 'has_purchase', legend: string) => (
    <SegmentedControl
      label={legend}
      showLabel
      options={[
        { value: 'any', label: t('filters.any') },
        { value: 'yes', label: t('filters.yes') },
        { value: 'no', label: t('filters.no') },
      ]}
      value={params[key] ?? 'any'}
      onChange={(value) => setParams({ [key]: value === 'any' ? undefined : value })}
    />
  );

  const active = activeFilterCount(params);
  // the user's codes in their order, then any code of the URL they do not have (any more)
  const codes = locations.map((location) => location.code);
  const locationCodes = [
    ...codes,
    ...(params.location ?? []).filter((code) => !codes.includes(code)),
  ];

  return (
    <div className={styles.body}>
      {chips(
        'set',
        t('filters.set'),
        sortSetsNewestFirst(meta?.sets ?? [], (set) => set.released_on).map((set) => set.id),
        (v) => v,
        facets.set,
      )}
      {chips('domain', t('filters.domain'), meta?.domains ?? [], (v) => label('domain', v))}
      {chips('type', t('filters.type'), meta?.types ?? [], (v) => label('type', v))}
      {chips(
        'rarity',
        t('filters.rarity'),
        meta?.rarities ?? [],
        (v) => label('rarity', v),
        facets.rarity,
      )}
      <SegmentedControl
        label={t('filters.foil')}
        showLabel
        options={[
          { value: 'any', label: t('filters.foilAny') },
          { value: 'foil', label: t('filters.foilOnly') },
          { value: 'nonfoil', label: t('filters.nonfoilOnly') },
        ]}
        value={params.foil ?? 'any'}
        onChange={(value) => setParams({ foil: value === 'any' ? undefined : value })}
      />
      {tri('selling', t('filters.selling'))}
      {chips(
        'condition',
        t('filters.condition'),
        meta?.conditions ?? [],
        (v) => label('condition', v),
        facets.condition,
      )}
      {chips(
        'language',
        t('filters.language'),
        meta?.languages ?? [],
        (v) => label('language', v),
        facets.language,
      )}
      {locationCodes.length > 0 &&
        chips('location', t('filters.location'), locationCodes, (v) => v)}
      {tri('has_purchase', t('filters.hasPurchase'))}
      <div className={styles.footer}>
        <Button variant="ghost" disabled={active === 0} onClick={onClear}>
          {t('clearFilters')}
        </Button>
        {variant === 'sheet' && onClose && (
          <Button onClick={onClose}>{t('filters.show', { count: total })}</Button>
        )}
      </div>
    </div>
  );
}
