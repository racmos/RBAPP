import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import { useOffline } from '@/auth';
import { useSearchNavigation } from '@/catalog';
import { useDocumentTitle } from '@/i18n';
import {
  parseProductSearch,
  parseTab,
  productsSearch,
  withChange,
  type ProductsParams,
  type ProductsTab,
} from './params';
import { useMyProducts } from './queries';

/**
 * Everything the two layouts of `/products` share: the tab, the URL params, the owned lines.
 * The tab comes from `?tab=`; without it the page opens on the user's products when they own
 * any, else on the catalog (F14-e S2).
 */
export function useProductsScreen() {
  const { t } = useTranslation('products');
  useDocumentTitle(t('title'));
  const offline = useOffline();
  const [searchParams] = useSearchParams();
  const { current, go: navigateSearch } = useSearchNavigation();
  const params = useMemo(() => parseProductSearch(searchParams), [searchParams]);
  const mine = useMyProducts();

  const asked = parseTab(searchParams);
  const fallback: ProductsTab | null = mine.data
    ? mine.data.total.lines > 0
      ? 'mine'
      : 'catalog'
    : mine.isError
      ? 'catalog'
      : null;
  const tab = asked ?? fallback;

  /**
   * A filter, sort or page change; it always shows the catalog, which it applies to. It starts
   * from the latest URL asked for, which the page may not have rendered yet (L6).
   */
  const setParams = useCallback(
    (patch: Partial<ProductsParams>, options: { replace?: boolean } = {}) =>
      navigateSearch(
        productsSearch('catalog', withChange(parseProductSearch(current()), patch)),
        options,
      ),
    [navigateSearch, current],
  );
  const choose = (next: ProductsTab) => {
    if (next !== tab) navigateSearch(productsSearch(next, parseProductSearch(current())));
  };

  return { t, offline, params, setParams, tab, choose, mine };
}

export type ProductsScreen = ReturnType<typeof useProductsScreen>;
