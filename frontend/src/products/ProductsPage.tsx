import { useCallback, useMemo, useRef, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useSearchParams } from 'react-router';
import type { ProductListParams } from '@/api/types';
import { useOffline } from '@/auth';
import { PageHeader } from '@/components/ui/PageHeader';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle } from '@/i18n';
import { CatalogTab } from './CatalogTab';
import { MineTab } from './MineTab';
import {
  parseProductSearch,
  parseTab,
  productsSearch,
  withChange,
  type ProductsTab,
} from './params';
import { useMyProducts } from './queries';
import styles from './ProductsPage.module.css';

const TABS: ProductsTab[] = ['mine', 'catalog'];

/**
 * `/products` (F14-e S2): "Mis productos" and "Catálogo" as tabs. The tab comes from `?tab=`;
 * without it the page opens on the user's products when they own any, else on the catalog.
 */
export function ProductsPage() {
  const { t } = useTranslation('products');
  useDocumentTitle(t('title'));
  const offline = useOffline();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const params = useMemo(() => parseProductSearch(searchParams), [searchParams]);
  const mine = useMyProducts();
  const tabRefs = useRef<Partial<Record<ProductsTab, HTMLButtonElement | null>>>({});

  const asked = parseTab(searchParams);
  const fallback: ProductsTab | null = mine.data
    ? mine.data.total.lines > 0
      ? 'mine'
      : 'catalog'
    : mine.isError
      ? 'catalog'
      : null;
  const tab = asked ?? fallback;

  const go = useCallback(
    (next: ProductsTab, nextParams: ProductListParams, options: { replace?: boolean } = {}) =>
      navigate(
        { pathname: location.pathname, search: `?${productsSearch(next, nextParams)}` },
        { replace: options.replace },
      ),
    [navigate, location.pathname],
  );
  const setParams = useCallback(
    (patch: Partial<ProductListParams>, options: { replace?: boolean } = {}) =>
      go('catalog', withChange(params, patch), options),
    [go, params],
  );
  const choose = (next: ProductsTab) => {
    if (next !== tab) void go(next, params);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = TABS.indexOf(tab ?? 'mine');
    let next: ProductsTab | undefined;
    if (event.key === 'ArrowRight') next = TABS[(index + 1) % TABS.length];
    else if (event.key === 'ArrowLeft') next = TABS[(index - 1 + TABS.length) % TABS.length];
    else if (event.key === 'Home') next = TABS[0];
    else if (event.key === 'End') next = TABS[TABS.length - 1];
    if (!next) return;
    event.preventDefault();
    choose(next);
    tabRefs.current[next]?.focus();
  };

  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} />
      <div role="tablist" aria-label={t('title')} className={styles.tabs}>
        {TABS.map((name) => (
          <button
            key={name}
            ref={(node) => {
              tabRefs.current[name] = node;
            }}
            type="button"
            role="tab"
            id={`products-tab-${name}`}
            aria-controls={`products-panel-${name}`}
            aria-selected={tab === name}
            tabIndex={tab === name || (tab === null && name === 'mine') ? 0 : -1}
            className={styles.tab}
            onClick={() => choose(name)}
            onKeyDown={onKeyDown}
          >
            {t(`tabs.${name}`)}
          </button>
        ))}
      </div>
      {tab === null ? (
        <Skeleton label={t('loading')} lines={5} />
      ) : (
        <div
          role="tabpanel"
          id={`products-panel-${tab}`}
          aria-labelledby={`products-tab-${tab}`}
          className={styles.panel}
        >
          {tab === 'mine' ? (
            <MineTab offline={offline} onBrowse={() => choose('catalog')} />
          ) : (
            <CatalogTab params={params} setParams={setParams} />
          )}
        </div>
      )}
    </div>
  );
}
