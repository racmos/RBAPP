import { useId, useState, type HTMLAttributes, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { readStorage, writeStorage } from '@/lib/storage';
import { Icon } from './Icon';
import styles from './SidePanel.module.css';

export type SidePanelKind = 'filters' | 'detail' | 'editor' | 'menu' | 'preview';

type SidePanelProps = Omit<HTMLAttributes<HTMLElement>, 'children' | 'className' | 'aria-label'> & {
  /** Remembers the collapsed state under `rb_panel_<id>_v1`. */
  id: string;
  /** Names the toggle: "Ocultar filtros", "Mostrar detalle"... */
  kind: SidePanelKind;
  /** Accessible name of the region. */
  label: string;
  /** Which side of the page it sits on; the chevron points the way it folds. */
  side?: 'start' | 'end';
  as?: 'aside' | 'nav';
  /** The caller's look and width; collapsed, the panel shrinks to its toggle whatever it says. */
  className?: string;
  /** The layout of the content (flex, gap, padding); it is `display: none` while collapsed. */
  contentClassName?: string;
  children: ReactNode;
};

const storageKey = (id: string) => `rb_panel_${id}_v1`;

/**
 * A panel at a side of the page that the user can fold away (owner feedback S23): filters,
 * details, editors and the admin menu. The content stays mounted (its inputs keep their state)
 * and is `hidden` while collapsed; the caller's grid gives the side column `auto`, so the main
 * column takes the freed width.
 */
export function SidePanel({
  id,
  kind,
  label,
  side = 'start',
  as: Element = 'aside',
  className,
  contentClassName,
  children,
  ...rest
}: SidePanelProps) {
  const { t } = useTranslation('common');
  const contentId = useId();
  const [collapsed, setCollapsed] = useState(() => readStorage(storageKey(id)) === 'collapsed');

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    writeStorage(storageKey(id), next ? 'collapsed' : 'expanded');
  };

  const name = t(collapsed ? `sidePanel.show.${kind}` : `sidePanel.hide.${kind}`);
  return (
    <Element
      {...rest}
      aria-label={label}
      data-side={side}
      data-collapsed={collapsed || undefined}
      className={[styles.root, className].filter(Boolean).join(' ')}
    >
      <div className={styles.bar}>
        <button
          type="button"
          className={styles.toggle}
          aria-expanded={!collapsed}
          aria-controls={contentId}
          aria-label={name}
          title={name}
          onClick={toggle}
        >
          <Icon name="arrow" size={16} className={styles.chevron} />
        </button>
      </div>
      <div
        id={contentId}
        className={[styles.content, contentClassName].filter(Boolean).join(' ')}
        hidden={collapsed}
      >
        {children}
      </div>
    </Element>
  );
}
