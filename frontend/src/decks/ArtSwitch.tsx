import { useId, useMemo, useState, type RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardMini, DeckCard } from '@/api/types';
import { useCardDetail } from '@/catalog';
import { CardImage, RarityDot } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Icon } from '@/components/ui/Icon';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatMoney } from '@/lib/format';
import { printingCard } from './editor';
import { Guarded } from './Guarded';
import { cardLabel } from './labels';
import type { DeckEditor, PrintingMove } from './useDeckEditor';
import styles from './ArtSwitch.module.css';

/** The zones whose printings can change; a slot or a battlefield holds one copy. */
export type ArtZone =
  'legend' | 'champion' | 'main' | 'battlefields' | 'runes' | 'sideboard' | 'workbench';
type LineZone = 'main' | 'runes' | 'sideboard' | 'workbench';
const isLineZone = (zone: ArtZone): zone is LineZone =>
  zone === 'main' || zone === 'runes' || zone === 'sideboard' || zone === 'workbench';

/** The row the art switch was opened from: its printing and its section. */
export type ArtTarget = { zone: ArtZone; card: DeckCard };

/** Copies of each printing (key) in a zone of lines. */
function countsIn(editor: DeckEditor, zone: LineZone): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const line of editor.content[zone]) counts[`${line.set}-${line.id}`] = line.qty;
  return counts;
}

/** Thumb, printing code, rarity, price and the caller's copies of one printing. */
function PrintingFacts({ printing, source }: { printing: CardMini; source: boolean }) {
  const { t } = useTranslation('decks');
  const image = useMemo(() => ({ ...printing, energy: null, might: null }), [printing]);
  return (
    <>
      <CardImage card={image} size="thumb" decorative className={styles.thumb} />
      <span className={styles.facts}>
        <span className={styles.code}>{printing.key}</span>
        <RarityDot rarity={printing.rarity} showLabel />
        <span>{printing.market === null ? t('row.noPrice') : formatMoney(printing.market)}</span>
        <span>{t('art.owned', { count: printing.owned_total })}</span>
        {source && <span className={styles.source}>{t('art.source')}</span>}
      </span>
    </>
  );
}

type ChoicesProps = { target: ArtTarget; editor: DeckEditor; onDone: () => void };

/** A zone of lines: each copy of the name goes to a printing. The copies come from (and go back
 *  to) the row's printing, so the section keeps the same number of copies. */
function LineChoices({
  target,
  editor,
  onDone,
  printings,
}: ChoicesProps & { printings: CardMini[] }) {
  const { t } = useTranslation('decks');
  const zone = target.zone as LineZone;
  const source = target.card;
  const name = cardLabel(source);
  const initial = countsIn(editor, zone);
  const [moved, setMoved] = useState<Record<string, number>>({});
  const others = printings.filter((p) => p.key !== source.key);
  const countOf = (key: string) =>
    key === source.key
      ? (initial[key] ?? 0) - others.reduce((total, p) => total + (moved[p.key] ?? 0), 0)
      : (initial[key] ?? 0) + (moved[key] ?? 0);
  const total = printings.reduce((sum, p) => sum + countOf(p.key), 0);
  const step = (key: string, by: number) =>
    setMoved((current) => ({ ...current, [key]: (current[key] ?? 0) + by }));
  const apply = () => {
    const card = (printing: CardMini) =>
      editor.book[printing.key] ?? printingCard(source, printing);
    const moves: PrintingMove[] = [];
    // copies back to the source first, so it has them to give
    for (const p of others) {
      const n = moved[p.key] ?? 0;
      if (n < 0) moves.push({ from: card(p), to: source, n: -n });
    }
    for (const p of others) {
      const n = moved[p.key] ?? 0;
      if (n > 0) moves.push({ from: source, to: card(p), n });
    }
    if (moves.length > 0) editor.changeArt(zone, moves);
    onDone();
  };
  const left = countOf(source.key);
  return (
    <>
      <p className={styles.hint}>{t('art.hint', { code: source.key })}</p>
      <p className={styles.hint}>{t('art.total', { count: total, name })}</p>
      <ul className={styles.list} aria-label={t('art.lines', { name })}>
        {printings.map((printing) => {
          const isSource = printing.key === source.key;
          const count = countOf(printing.key);
          return (
            <li
              key={printing.key}
              className={styles.item}
              data-source={isSource ? 'true' : undefined}
            >
              <PrintingFacts printing={printing} source={isSource} />
              <span className={styles.stepper}>
                {!isSource && (
                  <Guarded
                    label={t('art.less', { code: printing.key })}
                    reason={null}
                    disabled={count <= 0}
                    onClick={() => step(printing.key, -1)}
                  >
                    <Icon name="minus" size={16} />
                  </Guarded>
                )}
                <span className={styles.count}>{t('art.copies', { count })}</span>
                {!isSource && (
                  <Guarded
                    label={t('art.more', { code: printing.key })}
                    reason={left > 0 ? null : t('art.noneLeft', { code: source.key })}
                    disabled={false}
                    onClick={() => step(printing.key, 1)}
                  >
                    <Icon name="plus" size={16} />
                  </Guarded>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      <Footer editor={editor} onCancel={onDone} onApply={apply} />
    </>
  );
}

/** A slot or a battlefield holds one copy: one printing is chosen. */
function SlotChoices({
  target,
  editor,
  onDone,
  printings,
}: ChoicesProps & { printings: CardMini[] }) {
  const { t } = useTranslation('decks');
  const id = useId();
  const source = target.card;
  const [chosen, setChosen] = useState(source.key);
  const apply = () => {
    const printing = printings.find((p) => p.key === chosen);
    if (printing && chosen !== source.key) {
      const to = editor.book[printing.key] ?? printingCard(source, printing);
      editor.changeArt(target.zone as 'legend' | 'champion' | 'battlefields', [
        { from: source, to, n: 1 },
      ]);
    }
    onDone();
  };
  return (
    <>
      <p className={styles.hint}>{t('art.slotHint')}</p>
      <fieldset className={styles.fieldset}>
        <legend className="sr-only">{t('art.lines', { name: cardLabel(source) })}</legend>
        <ul className={styles.list}>
          {printings.map((printing) => (
            <li key={printing.key}>
              <label className={styles.item} data-source={chosen === printing.key || undefined}>
                <input
                  type="radio"
                  name={id}
                  value={printing.key}
                  checked={chosen === printing.key}
                  onChange={() => setChosen(printing.key)}
                  className={styles.radio}
                />
                <PrintingFacts printing={printing} source={printing.key === source.key} />
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <Footer editor={editor} onCancel={onDone} onApply={apply} />
    </>
  );
}

function Footer({
  editor,
  onCancel,
  onApply,
}: {
  editor: DeckEditor;
  onCancel: () => void;
  onApply: () => void;
}) {
  const { t } = useTranslation('decks');
  return (
    <div className={styles.footer}>
      <Button variant="ghost" onClick={onCancel}>
        {t('art.cancel')}
      </Button>
      <Button onClick={onApply} disabled={!editor.canEdit}>
        {t('art.apply')}
      </Button>
    </div>
  );
}

/** The printings of the row's card (`GET /cards/<set>/<id>`), then the choice for its zone. */
function ArtChoices({ target, editor, onDone }: ChoicesProps) {
  const { t } = useTranslation('decks');
  const detail = useCardDetail(target.card.set_id, target.card.card_id);
  if (detail.isPending) return <Skeleton label={t('art.loading')} lines={4} />;
  if (!detail.data) {
    return <ErrorState message={t('art.error')} onRetry={() => void detail.refetch()} />;
  }
  const printings = detail.data.printings;
  return isLineZone(target.zone) ? (
    <LineChoices target={target} editor={editor} onDone={onDone} printings={printings} />
  ) : (
    <SlotChoices target={target} editor={editor} onDone={onDone} printings={printings} />
  );
}

type ArtSwitchProps = {
  /** The row it was opened from; null when closed. */
  target: ArtTarget | null;
  editor: DeckEditor;
  onClose: () => void;
  /** The opener, or the section when the row is gone after the change. */
  returnFocusRef: RefObject<HTMLElement | null>;
};

/**
 * The art switch (owner request: a deck holds the exact printing it will take from the
 * collection). Opened from a row's "N alt arts", it lists every printing of the card; in a zone
 * of lines each copy goes to a printing, in a slot or a battlefield one printing is chosen. Apply
 * is one edit (autosaved, with undo); Cancel changes nothing.
 */
export function ArtSwitch({ target, editor, onClose, returnFocusRef }: ArtSwitchProps) {
  const { t } = useTranslation('decks');
  const title = target
    ? t('art.title', { name: cardLabel(target.card), section: t(`section.${target.zone}`) })
    : '';
  return (
    <Modal open={target !== null} onClose={onClose} title={title} returnFocusRef={returnFocusRef}>
      {target && (
        <ArtChoices
          key={`${target.zone}-${target.card.key}`}
          target={target}
          editor={editor}
          onDone={onClose}
        />
      )}
    </Modal>
  );
}
