import { useCallback, useId, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardFacets, CardListParams, GameMeta } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ChipGroup, FilterChip } from '@/components/ui/FilterChip';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { useEnumLabel } from '@/i18n';
import { domainColor, rarityColor } from '@/lib/domains';
import { readStorage, writeStorage } from '@/lib/storage';
import { DebouncedInput } from './DebouncedInput';
import styles from './CatalogFilters.module.css';

const INPUT_DEBOUNCE_MS = 300;
const FACET_STORAGE_KEY = 'rb_cards_facets';

const GROUP_IDS = [
  'set',
  'domain',
  'type',
  'supertype',
  'rarity',
  'energy',
  'power',
  'might',
  'price',
  'owned',
  'banned',
  'base',
  'text',
  'tags',
] as const;

type GroupId = (typeof GROUP_IDS)[number];

export type CatalogFiltersProps = {
  mode: 'sheet' | 'sidebar';
  params: CardListParams;
  setParams: (patch: Partial<CardListParams>) => void;
  meta: GameMeta | undefined;
  facets: CardFacets;
  total: number;
  activeCount: number;
  resultsRef?: React.RefObject<HTMLElement | null>;
  onClose?: () => void;
  onClear: () => void;
  isBusy?: boolean;
};

function readOpenGroups(): GroupId[] {
  const all = [...GROUP_IDS];
  try {
    const raw = readStorage(FACET_STORAGE_KEY);
    if (!raw) return all;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return all;
    return all.filter((id) => parsed.includes(id));
  } catch {
    return all;
  }
}

function writeOpenGroups(groups: GroupId[]): void {
  writeStorage(FACET_STORAGE_KEY, JSON.stringify(groups));
}

export function CatalogFilters({
  mode,
  params,
  setParams,
  meta,
  facets,
  activeCount,
  onClear,
  isBusy,
}: CatalogFiltersProps) {
  const { t } = useTranslation('cards');
  const { label } = useEnumLabel();

  const [openGroups, setOpenGroups] = useState<GroupId[]>(() => readOpenGroups());

  const toggleGroup = (id: GroupId) => {
    setOpenGroups((prev) => {
      const next = prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id];
      writeOpenGroups(next);
      return next;
    });
  };

  const toggleArray = useCallback(
    (
      key: 'set' | 'domain' | 'type' | 'supertype' | 'exclude_supertype' | 'rarity' | 'tag',
      value: string,
    ) => {
      const current = params[key] ?? [];
      if (current.includes(value)) {
        setParams({ [key]: current.filter((v) => v !== value) });
      } else {
        setParams({ [key]: [...current, value] });
      }
    },
    [params, setParams],
  );

  const showCount = useCallback(
    (facet: Record<string, number> | undefined, value: string): number | undefined => {
      const count = facet?.[value];
      return count === undefined ? undefined : count;
    },
    [],
  );

  const renderSet = (variant: 'sheet' | 'sidebar') => (
    <div className={styles.group}>
      {variant === 'sheet' ? (
        <fieldset className={styles.fieldset}>
          <legend className={styles.legend}>{t('catalog.facet.set')}</legend>
          <div className={styles.checkList}>
            {meta?.sets.map((set) => (
              <Checkbox
                key={set.id}
                label={`${set.name} (${showCount(facets.set, set.id) ?? 0})`}
                checked={params.set?.includes(set.id) ?? false}
                onChange={() => toggleArray('set', set.id)}
              />
            ))}
          </div>
        </fieldset>
      ) : (
        <div className={styles.checkList}>
          {meta?.sets.map((set) => (
            <Checkbox
              key={set.id}
              label={`${set.name} (${showCount(facets.set, set.id) ?? 0})`}
              checked={params.set?.includes(set.id) ?? false}
              onChange={() => toggleArray('set', set.id)}
            />
          ))}
        </div>
      )}
    </div>
  );

  const renderDomain = () => (
    <>
      <ChipGroup legend={t('catalog.facet.domain')}>
        {meta?.domains.map((domain) => {
          const selected = params.domain?.includes(domain) ?? false;
          const count = showCount(facets.domain, domain);
          return (
            <FilterChip
              key={domain}
              label={label('domain', domain)}
              count={count}
              pressed={selected}
              color={domainColor(domain)}
              onClick={() => toggleArray('domain', domain)}
            />
          );
        })}
      </ChipGroup>
      <div className={styles.matchControl}>
        <SegmentedControl
          label={t('catalog.facet.domainMatch')}
          options={[
            { value: 'any', label: t('catalog.facet.any') },
            { value: 'all', label: t('catalog.facet.all') },
            { value: 'subset', label: t('catalog.facet.subset') },
          ]}
          value={params.domain_match ?? 'any'}
          onChange={(value) => setParams({ domain_match: value as 'any' | 'all' | 'subset' })}
        />
      </div>
    </>
  );

  const renderType = () => (
    <ChipGroup legend={t('catalog.facet.type')}>
      {meta?.types.map((type) => {
        const selected = params.type?.includes(type) ?? false;
        return (
          <FilterChip
            key={type}
            label={label('type', type)}
            count={showCount(facets.type, type)}
            pressed={selected}
            onClick={() => toggleArray('type', type)}
          />
        );
      })}
    </ChipGroup>
  );

  const renderSupertype = () => (
    <ChipGroup legend={t('catalog.facet.supertype')}>
      {meta?.supertypes.map((supertype) => {
        const selected = params.supertype?.includes(supertype) ?? false;
        return (
          <FilterChip
            key={supertype}
            label={label('supertype', supertype)}
            count={showCount(facets.supertype, supertype)}
            pressed={selected}
            onClick={() => toggleArray('supertype', supertype)}
          />
        );
      })}
    </ChipGroup>
  );

  const renderRarity = () => (
    <ChipGroup legend={t('catalog.facet.rarity')}>
      {meta?.rarities.map((rarity) => {
        const selected = params.rarity?.includes(rarity) ?? false;
        return (
          <FilterChip
            key={rarity}
            label={label('rarity', rarity)}
            count={showCount(facets.rarity, rarity)}
            pressed={selected}
            color={rarityColor(rarity)}
            onClick={() => toggleArray('rarity', rarity)}
          />
        );
      })}
    </ChipGroup>
  );

  const renderTags = () => (
    <ChipGroup legend={t('catalog.facet.tags')}>
      {facets.tag?.map(({ tag, count }) => {
        const selected = params.tag?.includes(tag) ?? false;
        return (
          <FilterChip
            key={tag}
            label={tag}
            count={count}
            pressed={selected}
            onClick={() => toggleArray('tag', tag)}
          />
        );
      })}
    </ChipGroup>
  );

  const renderRange = (
    rangeKey: 'energy' | 'power' | 'might' | 'price',
    minKey: 'energy_min' | 'power_min' | 'might_min' | 'price_min',
    maxKey: 'energy_max' | 'power_max' | 'might_max' | 'price_max',
    step?: number,
  ) => (
    <RangeGroup
      label={t(`catalog.facet.${rangeKey}` as never)}
      minKey={minKey}
      maxKey={maxKey}
      min={params[minKey]}
      max={params[maxKey]}
      step={step}
      onChange={setParams}
    />
  );

  const renderOwned = () => (
    <SegmentedControl
      options={[
        { value: 'any', label: t('catalog.facet.ownedAny') },
        { value: 'owned', label: t('catalog.facet.ownedOwned') },
        { value: 'missing', label: t('catalog.facet.ownedMissing') },
      ]}
      value={params.owned ?? 'any'}
      onChange={(value) => setParams({ owned: value as 'any' | 'owned' | 'missing' })}
    />
  );

  const renderBanned = () => (
    <Field label={t('catalog.facet.banned')}>
      {(props) => (
        <Select
          {...props}
          value={params.banned_in ?? ''}
          onChange={(event) =>
            setParams({
              banned_in: event.target.value
                ? (event.target.value as '1v1' | '2v2' | 'any')
                : undefined,
            })
          }
        >
          <option value="">{t('catalog.facet.bannedNone')}</option>
          <option value="1v1">{t('catalog.facet.banned1v1')}</option>
          <option value="2v2">{t('catalog.facet.banned2v2')}</option>
          <option value="any">{t('catalog.facet.bannedAny')}</option>
        </Select>
      )}
    </Field>
  );

  const renderBase = () => (
    <Switch
      label={t('catalog.facet.baseOnly')}
      checked={params.base_only ?? false}
      onCheckedChange={(checked) => setParams({ base_only: checked || undefined })}
    />
  );

  const renderText = () => (
    <Field label={t('catalog.facet.text')}>
      {(props) => (
        <DebouncedInput
          {...props}
          type="search"
          value={params.text ?? ''}
          delay={INPUT_DEBOUNCE_MS}
          onCommit={(next) => setParams({ text: next || undefined })}
        />
      )}
    </Field>
  );

  const groups: {
    id: GroupId;
    title: string;
    render: (variant: 'sheet' | 'sidebar') => React.ReactNode;
  }[] = useMemo(
    () => [
      { id: 'set', title: t('catalog.facet.set'), render: () => renderSet(mode) },
      { id: 'domain', title: t('catalog.facet.domain'), render: () => renderDomain() },
      { id: 'type', title: t('catalog.facet.type'), render: () => renderType() },
      { id: 'supertype', title: t('catalog.facet.supertype'), render: () => renderSupertype() },
      { id: 'rarity', title: t('catalog.facet.rarity'), render: () => renderRarity() },
      {
        id: 'energy',
        title: t('catalog.facet.energy'),
        render: () => renderRange('energy', 'energy_min', 'energy_max'),
      },
      {
        id: 'power',
        title: t('catalog.facet.power'),
        render: () => renderRange('power', 'power_min', 'power_max'),
      },
      {
        id: 'might',
        title: t('catalog.facet.might'),
        render: () => renderRange('might', 'might_min', 'might_max'),
      },
      {
        id: 'price',
        title: t('catalog.facet.price'),
        render: () => renderRange('price', 'price_min', 'price_max', 0.01),
      },
      { id: 'owned', title: t('catalog.facet.owned'), render: () => renderOwned() },
      { id: 'banned', title: t('catalog.facet.banned'), render: () => renderBanned() },
      { id: 'base', title: t('catalog.facet.baseOnly'), render: () => renderBase() },
      { id: 'text', title: t('catalog.facet.text'), render: () => renderText() },
      { id: 'tags', title: t('catalog.facet.tags'), render: () => renderTags() },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, label, mode, meta, facets, params, setParams, toggleArray, showCount],
  );

  if (mode === 'sheet') {
    return (
      <div className={styles.sheetBody}>
        {groups.map((group) => (
          <div key={group.id}>{group.render('sheet')}</div>
        ))}
      </div>
    );
  }

  return (
    <aside
      className={styles.sidebar}
      data-testid="catalog-sidebar"
      aria-label={t('catalog.filters.title')}
      aria-busy={isBusy || undefined}
    >
      {activeCount > 0 && (
        <div className={styles.sidebarHeader}>
          <Button variant="ghost" size="sm" onClick={onClear}>
            {t('catalog.filters.clearAll')}
          </Button>
        </div>
      )}
      <div className={styles.sidebarBody}>
        {groups.map((group) => (
          <Collapsible
            key={group.id}
            title={group.title}
            open={openGroups.includes(group.id)}
            onToggle={() => toggleGroup(group.id)}
          >
            {group.render('sidebar')}
          </Collapsible>
        ))}
      </div>
    </aside>
  );
}

function Collapsible({
  title,
  open,
  onToggle,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  const contentId = useId();
  return (
    <div className={styles.collapsible}>
      <button
        type="button"
        className={styles.groupToggle}
        aria-expanded={open}
        aria-controls={contentId}
        onClick={onToggle}
      >
        {title}
        <Icon name="arrow" size={14} className={open ? styles.chevronOpen : styles.chevron} />
      </button>
      {open && (
        <div id={contentId} className={styles.groupContent}>
          {children}
        </div>
      )}
    </div>
  );
}

type RangeGroupProps = {
  label: string;
  minKey: 'energy_min' | 'power_min' | 'might_min' | 'price_min';
  maxKey: 'energy_max' | 'power_max' | 'might_max' | 'price_max';
  min: number | undefined;
  max: number | undefined;
  step?: number;
  onChange: (patch: Partial<CardListParams>) => void;
};

function RangeGroup({ label, minKey, maxKey, min, max, step, onChange }: RangeGroupProps) {
  const { t } = useTranslation('cards');

  return (
    <fieldset className={styles.fieldset}>
      <legend className={styles.legend}>{label}</legend>
      <div className={styles.range}>
        <Field label={t('catalog.facet.min')}>
          {(props) => (
            <DebouncedInput
              {...props}
              type="number"
              min={0}
              max={99}
              step={step}
              value={min === undefined ? '' : String(min)}
              delay={INPUT_DEBOUNCE_MS}
              onCommit={(next) => onChange({ [minKey]: next === '' ? undefined : Number(next) })}
            />
          )}
        </Field>
        <Field label={t('catalog.facet.max')}>
          {(props) => (
            <DebouncedInput
              {...props}
              type="number"
              min={0}
              max={99}
              step={step}
              value={max === undefined ? '' : String(max)}
              delay={INPUT_DEBOUNCE_MS}
              onCommit={(next) => onChange({ [maxKey]: next === '' ? undefined : Number(next) })}
            />
          )}
        </Field>
      </div>
    </fieldset>
  );
}
