import { useMemo, useRef, useState, type RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Sheet } from '@/components/ui/Sheet';
import { CardBrowser, type BrowserZone } from './CardBrowser';
import type { DeckEditor } from './useDeckEditor';
import styles from './DeckView.module.css';

type AddCardsProps = {
  zone: BrowserZone;
  editor: DeckEditor;
  /** The slot already holds its card: no button (the sheet may still be closing). */
  full: boolean;
  /** Where focus goes when the button is gone on close (a slot just filled). */
  fallbackFocus: RefObject<HTMLElement | null>;
};

/**
 * A section's `Add cards` button on the one-column editor (F5-i decision 4): it opens the card
 * browser for that zone in a bottom sheet. The sheet stays open while cards are added, so several
 * go in a row and the section behind fills as they do; choosing a legend or champion closes it.
 */
export function AddCardsSheet({ zone, editor, full, fallbackFocus }: AddCardsProps) {
  const { t } = useTranslation('decks');
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  // read when the sheet closes, after a filled slot took the button away
  const returnFocus = useMemo(
    () => ({
      get current() {
        return button.current ?? fallbackFocus.current;
      },
    }),
    [fallbackFocus],
  );
  const close = () => setOpen(false);
  return (
    <>
      {!full && (
        <p className={styles.addCards}>
          <Button
            ref={button}
            variant="ghost"
            size="sm"
            aria-label={t('sheet.openIn', { zone: t(`zoneIn.${zone}`) })}
            onClick={() => setOpen(true)}
          >
            <Icon name="plus" size={16} />
            {t('sheet.open')}
          </Button>
        </p>
      )}
      <Sheet
        open={open}
        onClose={close}
        title={t('sheet.title', { section: t(`section.${zone}`) })}
        hideClose
        returnFocusRef={returnFocus}
      >
        <CardBrowser editor={editor} zone={zone} onChosen={close} />
        <div className={styles.sheetFooter}>
          <Button onClick={close}>{t('sheet.done')}</Button>
        </div>
      </Sheet>
    </>
  );
}
