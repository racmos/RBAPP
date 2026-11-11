import { useId, useState, type DragEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { Wishlist } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Popover } from '@/components/ui/Popover';
import { pushToast } from '@/components/ui/toastStore';
import { useWishlistError } from './errors';
import { usePatchWishlist } from './queries';
import type { WishlistsScreen } from './useWishlistsScreen';
import styles from './Wishlists.module.css';

const DRAG_TYPE = 'text/plain';

/** A control that is disabled for a reason: the reason is its description and its tooltip. */
function Reasoned({
  reason,
  children,
  ...rest
}: Parameters<typeof Button>[0] & { reason: string | null }) {
  const id = useId();
  return (
    <>
      <Button
        {...rest}
        title={reason ?? rest.title}
        disabled={rest.disabled || reason !== null}
        aria-describedby={reason ? id : undefined}
      >
        {children}
      </Button>
      {reason && (
        <span id={id} className="sr-only">
          {reason}
        </span>
      )}
    </>
  );
}

/** The star: filled on the default list (it cannot be taken off), "Make default" elsewhere. */
function Star({ list, offline }: { list: Wishlist; offline: boolean }) {
  const { t } = useTranslation('wishlists');
  const patch = usePatchWishlist();
  const message = useWishlistError();
  if (list.is_default) {
    return (
      <Reasoned
        variant="ghost"
        size="sm"
        className={styles.starOn}
        aria-label={t('menu.default')}
        aria-pressed
        reason={t('menu.defaultFixed')}
      >
        <Icon name="star" size={18} />
      </Reasoned>
    );
  }
  return (
    <Button
      variant="ghost"
      size="sm"
      className={styles.star}
      aria-label={t('menu.makeDefault')}
      aria-pressed={false}
      title={t('menu.makeDefault')}
      disabled={offline}
      pending={patch.isPending}
      onClick={() =>
        patch.mutate(
          { id: list.id, body: { is_default: true } },
          {
            onSuccess: () =>
              pushToast({ kind: 'success', message: t('starred', { name: list.name }) }),
            onError: (error) => pushToast({ kind: 'error', message: message(error) }),
          },
        )
      }
    >
      <Icon name="star" size={18} />
    </Button>
  );
}

export type ListActions = {
  onNew: () => void;
  onRename: (list: Wishlist) => void;
  onDelete: (list: Wishlist) => void;
};

/**
 * The lists of the user in their order (F3-j): open one, star the default, and per list a menu
 * with Rename, Move up, Move down and Delete. On a pointer device a list can be dragged.
 */
export function ListsMenu({
  s,
  actions,
  onOpened,
  draggable = false,
}: {
  s: WishlistsScreen;
  actions: ListActions;
  /** After a list was opened (the phone sheet closes). */
  onOpened?: () => void;
  draggable?: boolean;
}) {
  const { t, items, selected, offline, openList, moveBy, moveTo } = s;
  const [dragged, setDragged] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);

  const dragFor = (list: Wishlist, index: number) => ({
    onDragStart: (event: DragEvent) => {
      if (offline) return;
      setDragged(list.id);
      event.dataTransfer.setData(DRAG_TYPE, String(list.id));
      event.dataTransfer.effectAllowed = 'move';
    },
    onDragOver: (event: DragEvent) => {
      if (dragged === null) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      setOver(list.id);
    },
    onDrop: (event: DragEvent) => {
      event.preventDefault();
      const id = dragged ?? Number(event.dataTransfer.getData(DRAG_TYPE));
      setDragged(null);
      setOver(null);
      if (Number.isInteger(id) && id > 0) moveTo(id, index);
    },
    onDragEnd: () => {
      setDragged(null);
      setOver(null);
    },
  });

  return (
    <div className={styles.menu}>
      {draggable && !offline && <p className={styles.hint}>{t('menu.dragHint')}</p>}
      <ol className={styles.lists} aria-label={t('menu.title')}>
        {items.map((list, index) => (
          <li
            key={list.id}
            className={styles.listRow}
            data-drop-target={(over === list.id && dragged !== list.id) || undefined}
            draggable={draggable && !offline}
            {...dragFor(list, index)}
          >
            <Star list={list} offline={offline} />
            <button
              type="button"
              className={styles.openList}
              aria-current={selected?.id === list.id ? 'true' : undefined}
              onClick={() => {
                openList(list.id);
                onOpened?.();
              }}
            >
              <span className={styles.listName} data-slot="name">
                {list.name}
              </span>
              <span className={styles.listCount}>{t('count', { count: list.line_count })}</span>
            </button>
            <Popover
              title={list.name}
              size="sm"
              trigger={<Icon name="more" size={18} />}
              triggerLabel={t('menu.actions', { name: list.name })}
            >
              {(close) => (
                <div className={styles.rowMenu}>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={offline}
                    onClick={() => {
                      close();
                      actions.onRename(list);
                    }}
                  >
                    {t('menu.rename')}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={offline || index === 0}
                    onClick={() => moveBy(list.id, -1)}
                  >
                    {t('menu.moveUp')}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={offline || index === items.length - 1}
                    onClick={() => moveBy(list.id, 1)}
                  >
                    {t('menu.moveDown')}
                  </Button>
                  <Reasoned
                    variant="danger"
                    size="sm"
                    disabled={offline}
                    reason={list.is_default ? t('menu.deleteDefault') : null}
                    onClick={() => {
                      close();
                      actions.onDelete(list);
                    }}
                  >
                    {t('menu.delete')}
                  </Reasoned>
                </div>
              )}
            </Popover>
          </li>
        ))}
      </ol>
      <Button variant="ghost" block disabled={offline} onClick={actions.onNew}>
        <Icon name="plus" size={16} />
        {t('menu.new')}
      </Button>
    </div>
  );
}
