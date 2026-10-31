import { useRef, type KeyboardEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Skeleton } from '@/components/ui/Skeleton';
import type { ProductsTab } from './params';
import styles from './ProductsPage.module.css';

const TABS: ProductsTab[] = ['mine', 'catalog'];

type ProductTabsProps = {
  tab: ProductsTab | null;
  choose: (tab: ProductsTab) => void;
  /** The content of the selected tab. */
  children: ReactNode;
};

/** "My products" and "Catalog" as tabs (arrows, Home and End move between them), and the panel. */
export function ProductTabs({ tab, choose, children }: ProductTabsProps) {
  const { t } = useTranslation('products');
  const tabRefs = useRef<Partial<Record<ProductsTab, HTMLButtonElement | null>>>({});

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
    <>
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
          {children}
        </div>
      )}
    </>
  );
}
