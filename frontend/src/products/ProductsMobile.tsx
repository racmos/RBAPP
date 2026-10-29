import { PageHeader } from '@/components/ui/PageHeader';
import { CatalogTab } from './CatalogTab';
import { MineTab } from './MineTab';
import { ProductTabs } from './ProductTabs';
import type { ProductsScreen } from './useProductsScreen';
import styles from './ProductsPage.module.css';

/** The layout below 1240 px (F14-e S2): the tabs, the owned lines or the catalog tiles. */
export function ProductsMobile({ s }: { s: ProductsScreen }) {
  const { t, offline, params, setParams, tab, choose } = s;
  return (
    <div className={styles.page}>
      <PageHeader title={t('title')} />
      <ProductTabs tab={tab} choose={choose}>
        {tab === 'mine' ? (
          <MineTab offline={offline} onBrowse={() => choose('catalog')} />
        ) : (
          <CatalogTab params={params} setParams={setParams} />
        )}
      </ProductTabs>
    </div>
  );
}
