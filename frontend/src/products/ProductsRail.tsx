import { useTranslation } from 'react-i18next';
import { PRODUCT_KINDS, type ProductKind } from '@/api/types';
import { DebouncedInput } from '@/catalog';
import { Checkbox } from '@/components/ui/Checkbox';
import { Switch } from '@/components/ui/Switch';
import type { ProductsParams } from './params';
import { useProductList } from './queries';
import { SetSelect } from './SetSelect';
import styles from './ProductsDesktop.module.css';

const SEARCH_DELAY_MS = 300;

type ProductsRailProps = {
  params: ProductsParams;
  setParams: (patch: Partial<ProductsParams>, options?: { replace?: boolean }) => void;
};

/** The left rail from 1240 px (F14-f S1): search, kinds with counts, set and "only mine". */
export function ProductsRail({ params, setParams }: ProductsRailProps) {
  const { t } = useTranslation('products');
  const list = useProductList(params);
  const facets = list.data?.meta?.facets ?? { kind: {}, set: {} };
  const kinds = params.kind ?? [];

  const toggleKind = (kind: ProductKind, on: boolean) => {
    const next = on ? [...kinds, kind] : kinds.filter((item) => item !== kind);
    setParams({ kind: next.length > 0 ? next : undefined });
  };

  return (
    <div className={styles.railBody}>
      <form role="search" onSubmit={(event) => event.preventDefault()}>
        <label htmlFor="products-rail-search" className="sr-only">
          {t('search.label')}
        </label>
        <DebouncedInput
          id="products-rail-search"
          type="search"
          className={styles.railSearch}
          placeholder={t('search.placeholder')}
          value={params.q ?? ''}
          delay={SEARCH_DELAY_MS}
          onCommit={(q) => setParams({ q: q || undefined }, { replace: true })}
        />
      </form>

      <fieldset className={styles.kinds}>
        <legend className={styles.railLabel}>{t('filters.kind')}</legend>
        {PRODUCT_KINDS.filter((kind) => kind in facets.kind || kinds.includes(kind)).map((kind) => (
          <Checkbox
            key={kind}
            checked={kinds.includes(kind)}
            onChange={(event) => toggleKind(kind, event.target.checked)}
            label={
              <>
                {t(`kind.${kind}`)} <span className={styles.count}>({facets.kind[kind] ?? 0})</span>
              </>
            }
          />
        ))}
      </fieldset>

      <label className={styles.railField}>
        <span className={styles.railLabel}>{t('filters.set')}</span>
        <SetSelect params={params} setParams={setParams} facets={facets} />
      </label>

      <Switch
        label={t('filters.onlyMine')}
        checked={params.owned === 'owned'}
        onCheckedChange={(on) => setParams({ owned: on ? 'owned' : undefined })}
      />
    </div>
  );
}
