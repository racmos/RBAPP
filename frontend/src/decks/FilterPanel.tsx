import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardFacets, CardListParams, GameMeta } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { ChipGroup, FilterChip } from '@/components/ui/FilterChip';
import { Icon } from '@/components/ui/Icon';
import { Popover } from '@/components/ui/Popover';
import { Switch } from '@/components/ui/Switch';
import { useEnumLabel } from '@/i18n';
import { domainColor, rarityColor } from '@/lib/domains';
import { sortSetsNewestFirst } from '@/lib/sets';
import {
  NO_FILTERS,
  RANGES,
  RANGE_KEYS,
  countFilters,
  type BrowserFilters,
  type FilterScope,
  type RangeKey,
} from './browserFilters';
import styles from './CardBrowser.module.css';

type ListKey = 'domain' | 'type' | 'rarity' | 'set' | 'tag';

type FilterProps = {
  /** The filters that apply to the current zone (already pruned to `scope`). */
  filters: BrowserFilters;
  scope: FilterScope;
  /** The zone's own filters: a `subset` domain match hides the domain counts. */
  base: Partial<CardListParams>;
  facets: CardFacets | undefined;
  meta: GameMeta | undefined;
  onChange: (next: BrowserFilters) => void;
};

/** A facet's count, when the API sent that facet. */
const countIn = (facet: Record<string, number> | undefined, value: string) =>
  facet ? (facet[value] ?? 0) : undefined;

const rangeValues = (key: RangeKey) => Array.from({ length: RANGES[key] + 1 }, (_, i) => i);

function toggled(values: string[], value: string) {
  return values.includes(value) ? values.filter((v) => v !== value) : [...values, value];
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.filterSection}>
      <h4 className={styles.filterHeading}>{title}</h4>
      {children}
    </div>
  );
}

/** The tags a zone offers: the legend's (champion), else the tags of the answer plus the chosen. */
function tagOptions(filters: BrowserFilters, scope: FilterScope, facets: CardFacets | undefined) {
  if (scope.tags) return scope.tags;
  const listed = (facets?.tag ?? []).map(({ tag }) => tag);
  return [...listed, ...filters.tag.filter((tag) => !listed.includes(tag))];
}

/**
 * The `Filter` button of the card browser and its panel (F5-i step 3): groups Card, Cost &
 * Might, Advanced and Status of the owner's reference, limited to what the zone allows. Values
 * show the count of the current answer's facets when the API sends one.
 */
export function FilterPanel({ filters, scope, base, facets, meta, onChange }: FilterProps) {
  const { t } = useTranslation('decks');
  const { label } = useEnumLabel();
  const count = countFilters(filters);
  const toggle = (key: ListKey, value: string) =>
    onChange({ ...filters, [key]: toggled(filters[key], value) });

  const domains = scope.domains ?? meta?.domains ?? [];
  const domainCounts = base.domain_match === 'subset' ? undefined : facets?.domain;
  const types = scope.types ?? meta?.types ?? [];
  const sets = sortSetsNewestFirst(meta?.sets ?? [], (set) => set.released_on);
  const tags = tagOptions(filters, scope, facets);
  const tagCount = (tag: string) => facets?.tag?.find((item) => item.tag === tag)?.count;

  return (
    <Popover
      title={t('browser.filter.title')}
      triggerLabel={count > 0 ? t('browser.filter.openActive', { count }) : undefined}
      trigger={
        <>
          <Icon name="filter" size={16} />
          {t('browser.filter.open')}
          {count > 0 && (
            <span className={styles.filterCount} aria-hidden="true">
              {count}
            </span>
          )}
        </>
      }
    >
      <Section title={t('browser.filter.card')}>
        <ChipGroup legend={t('browser.filter.domain')}>
          {domains.map((domain) => (
            <FilterChip
              key={domain}
              label={label('domain', domain)}
              count={countIn(domainCounts, domain)}
              pressed={filters.domain.includes(domain)}
              color={domainColor(domain)}
              onClick={() => toggle('domain', domain)}
            />
          ))}
        </ChipGroup>
        {types.length > 0 && (
          <ChipGroup legend={t('browser.filter.type')}>
            {types.map((type) => (
              <FilterChip
                key={type}
                label={label('type', type)}
                count={countIn(facets?.type, type)}
                pressed={filters.type.includes(type)}
                onClick={() => toggle('type', type)}
              />
            ))}
          </ChipGroup>
        )}
        <ChipGroup legend={t('browser.filter.rarity')}>
          {(meta?.rarities ?? []).map((rarity) => (
            <FilterChip
              key={rarity}
              label={label('rarity', rarity)}
              count={countIn(facets?.rarity, rarity)}
              pressed={filters.rarity.includes(rarity)}
              color={rarityColor(rarity)}
              onClick={() => toggle('rarity', rarity)}
            />
          ))}
        </ChipGroup>
      </Section>
      {scope.costs && (
        <Section title={t('browser.filter.costs')}>
          {RANGE_KEYS.map((key) => (
            <ChipGroup key={key} legend={t(`browser.filter.${key}`)}>
              {rangeValues(key).map((value) => (
                <FilterChip
                  key={value}
                  label={value === RANGES[key] ? t('browser.filter.top', { value }) : String(value)}
                  pressed={filters[key] === value}
                  onClick={() =>
                    onChange({ ...filters, [key]: filters[key] === value ? null : value })
                  }
                />
              ))}
            </ChipGroup>
          ))}
        </Section>
      )}
      <Section title={t('browser.filter.advanced')}>
        <ChipGroup legend={t('browser.filter.set')}>
          {sets.map((set) => (
            <FilterChip
              key={set.id}
              label={set.name}
              count={countIn(facets?.set, set.id)}
              pressed={filters.set.includes(set.id)}
              onClick={() => toggle('set', set.id)}
            />
          ))}
        </ChipGroup>
        {tags.length > 0 && (
          <ChipGroup legend={t('browser.filter.tags')}>
            {tags.map((tag) => (
              <FilterChip
                key={tag}
                label={tag}
                count={tagCount(tag)}
                pressed={filters.tag.includes(tag)}
                onClick={() => toggle('tag', tag)}
              />
            ))}
          </ChipGroup>
        )}
      </Section>
      <Section title={t('browser.filter.status')}>
        <Switch
          label={t('browser.filter.owned')}
          checked={filters.owned}
          onCheckedChange={(owned) => onChange({ ...filters, owned })}
        />
      </Section>
      <div className={styles.filterFooter}>
        <Button
          variant="ghost"
          size="sm"
          disabled={count === 0}
          onClick={() => onChange(NO_FILTERS)}
        >
          {t('browser.filter.clear')}
        </Button>
      </div>
    </Popover>
  );
}

/** The chosen filters as removable chips under the search, with Clear filters. */
export function ActiveFilters({
  filters,
  meta,
  onChange,
}: Pick<FilterProps, 'filters' | 'meta' | 'onChange'>) {
  const { t } = useTranslation('decks');
  const { label } = useEnumLabel();
  const setName = (id: string) => meta?.sets.find((set) => set.id === id)?.name ?? id;
  const without = (key: ListKey, value: string) => () =>
    onChange({ ...filters, [key]: filters[key].filter((v) => v !== value) });
  const chips: { key: string; label: string; remove: () => void }[] = [
    ...filters.domain.map((v) => ({
      key: `domain-${v}`,
      label: label('domain', v),
      remove: without('domain', v),
    })),
    ...filters.type.map((v) => ({
      key: `type-${v}`,
      label: label('type', v),
      remove: without('type', v),
    })),
    ...filters.rarity.map((v) => ({
      key: `rarity-${v}`,
      label: label('rarity', v),
      remove: without('rarity', v),
    })),
    ...RANGE_KEYS.flatMap((key) => {
      const value = filters[key];
      if (value === null) return [];
      const shown = value === RANGES[key] ? t('browser.filter.top', { value }) : String(value);
      return [
        {
          key,
          label: t(`browser.filter.chip.${key}`, { value: shown }),
          remove: () => onChange({ ...filters, [key]: null }),
        },
      ];
    }),
    ...filters.set.map((v) => ({ key: `set-${v}`, label: setName(v), remove: without('set', v) })),
    ...filters.tag.map((v) => ({ key: `tag-${v}`, label: v, remove: without('tag', v) })),
    ...(filters.owned
      ? [
          {
            key: 'owned',
            label: t('browser.filter.owned'),
            remove: () => onChange({ ...filters, owned: false }),
          },
        ]
      : []),
  ];
  if (chips.length === 0) return null;
  return (
    <div className={styles.activeFilters}>
      <ul className={styles.chips} aria-label={t('browser.filter.active')}>
        {chips.map((chip) => (
          <li key={chip.key}>
            <FilterChip
              label={chip.label}
              onRemove={{
                'aria-label': t('browser.filter.remove', { label: chip.label }),
                onClick: chip.remove,
              }}
            />
          </li>
        ))}
      </ul>
      <Button variant="ghost" size="sm" onClick={() => onChange(NO_FILTERS)}>
        {t('browser.filter.clear')}
      </Button>
    </div>
  );
}
