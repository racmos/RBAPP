import { useMemo, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { CardImage } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import styles from './CardZoom.module.css';

type ZoomCard = Parameters<typeof CardImage>[0]['card'] & { key: string };

type ZoomProps = {
  card: ZoomCard;
  /** How the deck names the card (a legend reads `Tag, Name`). */
  name: string;
  className?: string;
  /** What the button shows: the thumbnail of a row, the magnifier of a tile. */
  children: ReactNode;
};

/**
 * A button that shows the card big enough to read (owner request: a tap on a deck card enlarges
 * it): the full image, the name and the printing (`OGN-310`) in a modal. Escape, the backdrop and
 * Close close it; focus goes back to the button. The click never reaches a parent control (a
 * browser tile adds the card on its own click).
 */
export function CardZoom({ card, name, className, children }: ZoomProps) {
  const { t } = useTranslation('decks');
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  const label = t('zoom.view', { name });
  // CardImage resets on a new card object: one per card and name
  const image = useMemo(() => ({ ...card, name }), [card, name]);
  return (
    <>
      <button
        ref={button}
        type="button"
        className={className}
        aria-label={label}
        title={label}
        onClick={(event) => {
          event.stopPropagation();
          setOpen(true);
        }}
      >
        {children}
      </button>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={name}
        hideClose
        returnFocusRef={button}
      >
        <figure className={styles.figure}>
          <CardImage card={image} size="full" priority className={styles.image} />
          <figcaption className={styles.code}>{card.key}</figcaption>
        </figure>
        <div className={styles.footer}>
          <Button data-autofocus onClick={() => setOpen(false)}>
            {t('zoom.close')}
          </Button>
        </div>
      </Modal>
    </>
  );
}
