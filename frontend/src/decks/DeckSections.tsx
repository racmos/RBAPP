import { useId, useMemo, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardListParams, DeckCard, DeckRef } from '@/api/types';
import { CardImage, DomainPips } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { CardCombobox } from '@/catalog';
import { useEnumLabel } from '@/i18n';
import { formatMoney } from '@/lib/format';
import type { EditZone } from './editor';
import { cardLabel, refKey } from './labels';
import { useRuneCards } from './queries';
import type { DeckEditor } from './useDeckEditor';
import styles from './DeckView.module.css';

/** The sections of the workspace in display order (design-handoff §3.7.1). */
export const SECTION_ORDER = [
  'legend',
  'champion',
  'main',
  'battlefields',
  'runes',
  'sideboard',
] as const;
type SectionKey = (typeof SECTION_ORDER)[number] | 'workbench';

type MoveZone = 'main' | 'sideboard' | 'workbench';
const MOVES: Record<MoveZone, MoveZone[]> = {
  main: ['sideboard', 'workbench'],
  sideboard: ['main', 'workbench'],
  workbench: ['main', 'sideboard'],
};

/** A control the rules may refuse: disabled, with the reason as tooltip and description. */
function Guarded({
  label,
  reason,
  disabled,
  onClick,
  children,
}: {
  label: string;
  reason: string | null;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        aria-label={label}
        title={reason ?? label}
        disabled={disabled || reason !== null}
        aria-describedby={reason ? id : undefined}
        onClick={onClick}
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

type RowProps = { card: DeckCard; qty: number; zone: SectionKey; editor?: DeckEditor };

/** One card: thumb, name, copies, type, domains and price; with an editor, its controls. */
export function CardRow({ card, qty, zone, editor }: RowProps) {
  const { t } = useTranslation('decks');
  const { typeLabel } = useEnumLabel();
  // CardImage resets on a new card object: keep one per printing
  const image = useMemo(() => ({ ...card, energy: null, might: null }), [card]);
  const ref: DeckRef = { set: card.set_id, id: card.card_id };
  const name = cardLabel(card);
  const off = !editor?.canEdit;
  return (
    <li className={styles.row}>
      <CardImage card={image} size="thumb" className={styles.thumb} />
      <span className={styles.rowMain}>
        <span className={styles.rowName} data-slot="name">
          {name}
        </span>
        <span className={styles.rowFacts}>
          <span>{typeLabel(card.supertype, card.type)}</span>
          <DomainPips domains={card.domains} size={16} />
        </span>
      </span>
      <span className={styles.qty} data-slot="qty">
        {t('row.qty', { qty })}
      </span>
      <span className={card.market === null ? styles.muted : styles.price}>
        {card.market === null ? t('row.noPrice') : formatMoney(card.market)}
      </span>
      {editor && (
        <span className={styles.controls}>
          {zone === 'legend' || zone === 'champion' || zone === 'battlefields' ? (
            <Guarded
              label={t('edit.remove', { name })}
              reason={null}
              disabled={off}
              onClick={() =>
                zone === 'battlefields' ? editor.remove(ref, zone) : editor.clearSlot(zone)
              }
            >
              <Icon name="trash" size={16} />
            </Guarded>
          ) : (
            <>
              <Guarded
                label={t('edit.removeCopy', { name })}
                reason={null}
                disabled={off}
                onClick={() => editor.remove(ref, zone)}
              >
                <Icon name="minus" size={16} />
              </Guarded>
              <Guarded
                label={t('edit.addCopy', { name })}
                reason={off ? null : editor.addReason(ref, zone)}
                disabled={off}
                onClick={() => editor.add(ref, zone)}
              >
                <Icon name="plus" size={16} />
              </Guarded>
              {zone !== 'runes' &&
                MOVES[zone].map((to) => (
                  <Guarded
                    key={to}
                    label={t('edit.move', { name, zone: t(`zoneIn.${to}`) })}
                    reason={off ? null : editor.moveReason(ref, zone, to)}
                    disabled={off}
                    onClick={() => editor.move(ref, zone, to)}
                  >
                    {t(`edit.moveShort.${to}`)}
                  </Guarded>
                ))}
            </>
          )}
        </span>
      )}
    </li>
  );
}

/** The `GET /cards` filters of each section's search (F5-h stage 2). */
function pickFilters(zone: SectionKey, editor: DeckEditor): Partial<CardListParams> {
  const legend = editor.content.legend ? editor.book[refKey(editor.content.legend)] : undefined;
  switch (zone) {
    case 'legend':
      return { type: ['Legend'] };
    case 'champion':
      return { type: ['Unit'], supertype: ['Champion'], tag: legend?.tags ?? [] };
    case 'runes':
      return { type: ['Rune'], domain: editor.identityDomains };
    case 'battlefields':
      return { type: ['Battlefield'] };
    case 'workbench':
      return {};
    default:
      return { type: ['Unit', 'Spell', 'Gear'], exclude_supertype: ['Token'] };
  }
}

function AutoRunes({ editor }: { editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  const runes = useRuneCards(editor.canEdit ? editor.identityDomains : []);
  const id = useId();
  return (
    <p className={styles.autoRunes}>
      <Button
        variant="ghost"
        size="sm"
        aria-describedby={id}
        disabled={!editor.canEdit || editor.identityDomains.length === 0 || !runes.data}
        onClick={() => editor.balanceRunes(runes.data?.data.items ?? [])}
      >
        {t('edit.autoRunes')}
      </Button>
      <span id={id} className={styles.muted}>
        {t('edit.autoRunesHint')}
      </span>
    </p>
  );
}

function Section({ name, editor }: { name: SectionKey; editor: DeckEditor }) {
  const { t } = useTranslation('decks');
  const { content, book, done } = editor;
  const lines =
    name === 'legend' || name === 'champion'
      ? content[name]
        ? [{ ...content[name], qty: 1 }]
        : []
      : name === 'battlefields'
        ? content.battlefields.map((ref) => ({ ...ref, qty: 1 }))
        : content[name];
  const rows = lines.flatMap((line) => {
    const card = book[refKey(line)];
    return card ? [{ card, qty: line.qty }] : [];
  });
  const sectionDone = name === 'workbench' ? null : done[name];
  const count = sectionDone
    ? `${sectionDone.have}/${sectionDone.need}`
    : String(rows.reduce((total, row) => total + row.qty, 0));
  const slotFull = (name === 'legend' || name === 'champion') && rows.length > 0;
  return (
    <details className={styles.section} open>
      <summary>
        <span className={styles.sectionName}>{t(`section.${name}`)}</span>
        <span className={styles.sectionCount}>{count}</span>
      </summary>
      {rows.length === 0 ? (
        <p className={styles.muted}>{t('emptySection')}</p>
      ) : (
        <ul className={styles.rows}>
          {rows.map((row) => (
            <CardRow key={row.card.key} {...row} zone={name} editor={editor} />
          ))}
        </ul>
      )}
      {name === 'runes' && <AutoRunes editor={editor} />}
      {editor.canEdit && !slotFull && (
        <CardCombobox
          className={styles.pick}
          label={t(`edit.pick.${name}`)}
          filters={pickFilters(name, editor)}
          onSelect={(card) => editor.pick(card, name as EditZone | 'legend' | 'champion')}
        />
      )}
    </details>
  );
}

/** Legend, Champion, Main deck, Battlefields, Runes, Sideboard; the workbench only with cards
 *  (the "To bench" moves fill it). */
export function DeckSections({ editor }: { editor: DeckEditor }) {
  const showBench = editor.content.workbench.length > 0;
  return (
    <div className={styles.sections}>
      {SECTION_ORDER.map((name) => (
        <Section key={name} name={name} editor={editor} />
      ))}
      {showBench && <Section name="workbench" editor={editor} />}
    </div>
  );
}
