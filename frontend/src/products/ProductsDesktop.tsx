import { useState } from 'react';
import { useNavigate } from 'react-router';
import { PageHeader } from '@/components/ui/PageHeader';
import { SidePanel } from '@/components/ui/SidePanel';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { CatalogTable } from './CatalogTable';
import { MineTable } from './MineTable';
import { ProductPanel } from './ProductPanel';
import { ProductsRail } from './ProductsRail';
import { ProductTabs } from './ProductTabs';
import type { ProductsScreen } from './useProductsScreen';
import styles from './ProductsDesktop.module.css';

/** The layout from 1240 px (F14-f): filter rail, the tabs with a table each, the wide panel. */
export function ProductsDesktop({ s }: { s: ProductsScreen }) {
  const { t, lang, offline, params, setParams, tab, choose } = s;
  const wide = useMediaQuery(up('2xl'));
  const navigate = useNavigate();
  const [selected, setSelected] = useState<number | null>(null);

  // From 1600 px a row shows its product in the panel; below it opens the product page.
  const activate = (id: number) => {
    if (wide) setSelected(id);
    else void navigate(`/products/${id}`);
  };

  return (
    <div className={styles.page}>
      <div className={styles.layout} data-wide={wide || undefined}>
        <SidePanel
          id="products-filters"
          kind="filters"
          label={t('filters.title')}
          className={styles.rail}
        >
          <ProductsRail params={params} setParams={setParams} />
        </SidePanel>

        <div className={styles.main}>
          <PageHeader title={t('title')} />
          <ProductTabs tab={tab} choose={choose}>
            {tab === 'mine' ? (
              <MineTable
                lang={lang}
                offline={offline}
                onBrowse={() => choose('catalog')}
                selected={wide ? selected : null}
                onActivate={activate}
              />
            ) : (
              <CatalogTable
                params={params}
                setParams={setParams}
                lang={lang}
                wide={wide}
                selected={wide ? selected : null}
                onActivate={activate}
              />
            )}
          </ProductTabs>
        </div>

        {wide && <ProductPanel id={selected} lang={lang} offline={offline} />}
      </div>
    </div>
  );
}
