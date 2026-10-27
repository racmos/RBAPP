import { useTranslation } from 'react-i18next';
import type { CardListParams } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import styles from './CatalogToolbar.module.css';

const SORT_KEYS: Array<NonNullable<CardListParams['sort']>> = [
  'number',
  'name',
  'price',
  'trend_7d',
  'trend_30d',
  'rarity',
  'energy',
  'power',
  'might',
];

const PER_PAGE_OPTIONS = [48, 96, 192] as const;

export type CatalogToolbarProps = {
  activeCount: number;
  total: number;
  showSidebar: boolean;
  showPageSize: boolean;
  sort: string;
  dir: 'asc' | 'desc';
  view: 'grid' | 'list' | 'table';
  perPage: 48 | 96 | 192;
  tableEnabled: boolean;
  onOpenFilters: () => void;
  onSortChange: (sort: CardListParams['sort']) => void;
  onDirChange: (dir: 'asc' | 'desc') => void;
  onViewChange: (view: 'grid' | 'list' | 'table') => void;
  onPerPageChange: (perPage: 48 | 96 | 192) => void;
};

export function CatalogToolbar({
  activeCount,
  total,
  showSidebar,
  showPageSize,
  sort,
  dir,
  view,
  perPage,
  tableEnabled,
  onOpenFilters,
  onSortChange,
  onDirChange,
  onViewChange,
  onPerPageChange,
}: CatalogToolbarProps) {
  const { t } = useTranslation('cards');

  const translateKey = (key: string) => (t as (key: string) => string)(key);
  const sortOptions = SORT_KEYS.map((key) => ({
    value: key,
    label: translateKey(`catalog.sort.${key}`),
  }));

  return (
    <div className={styles.toolbar}>
      {showSidebar ? (
        <span className={styles.count}>
          {total === 1
            ? t('catalog.count_one', { count: total })
            : t('catalog.count_other', { count: total })}
        </span>
      ) : (
        <Button variant="ghost" size="sm" onClick={onOpenFilters} className={styles.filterButton}>
          {t('catalog.filters.open')}
          {activeCount > 0 && (
            <span className={styles.badge}>
              {activeCount === 1
                ? t('catalog.filters.active_one', { count: activeCount })
                : t('catalog.filters.active_other', { count: activeCount })}
            </span>
          )}
        </Button>
      )}

      <Field label={t('catalog.sort.label')}>
        {(props) => (
          <Select
            {...props}
            value={sort}
            onChange={(event) => onSortChange(event.target.value as CardListParams['sort'])}
          >
            {sortOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <button
        type="button"
        className={styles.dirButton}
        aria-pressed={dir === 'desc'}
        aria-label={t('catalog.sort.dirLabel')}
        onClick={() => onDirChange(dir === 'asc' ? 'desc' : 'asc')}
      >
        <Icon name="arrow" size={16} className={dir === 'desc' ? styles.dirDesc : styles.dirAsc} />
      </button>

      {showPageSize && (
        <Field label={t('catalog.perPage')}>
          {(props) => (
            <Select
              {...props}
              value={perPage}
              onChange={(event) => onPerPageChange(Number(event.target.value) as 48 | 96 | 192)}
            >
              {PER_PAGE_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}

      <SegmentedControl
        label={t('catalog.view.label')}
        options={[
          { value: 'grid', label: t('catalog.view.grid') },
          { value: 'list', label: t('catalog.view.list') },
          { value: 'table', label: t('catalog.view.table'), disabled: !tableEnabled },
        ]}
        value={view}
        onChange={onViewChange}
      />
    </div>
  );
}
