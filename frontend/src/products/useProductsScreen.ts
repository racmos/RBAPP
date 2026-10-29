import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useSearchParams } from 'react-router';
import { useOffline } from '@/auth';
import { useDocumentTitle } from '@/i18n';
import { langOf } from './format';
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
  const { t, i18n } = useTranslation('products');
  useDocumentTitle(t('title'));
  const lang = langOf(i18n.language);
  const offline = useOffline();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
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

  const go = useCallback(
    (next: ProductsTab, nextParams: ProductsParams, options: { replace?: boolean } = {}) =>
      navigate(
        { pathname: location.pathname, search: `?${productsSearch(next, nextParams)}` },
        { replace: options.replace },
      ),
    [navigate, location.pathname],
  );
  /** A filter, sort or page change; it always shows the catalog, which it applies to. */
  const setParams = useCallback(
    (patch: Partial<ProductsParams>, options: { replace?: boolean } = {}) =>
      go('catalog', withChange(params, patch), options),
    [go, params],
  );
  const choose = (next: ProductsTab) => {
    if (next !== tab) void go(next, params);
  };

  return { t, lang, offline, params, setParams, tab, choose, mine };
}

export type ProductsScreen = ReturnType<typeof useProductsScreen>;
