import { useTranslation } from 'react-i18next';
import type { CardMini, WishlistLine } from '@/api/types';
import { DebouncedInput } from '@/catalog';
import { MoneyField } from '@/collection/MoneyField';
import { Stepper } from '@/collection/Stepper';
import { CardImage } from '@/components/card';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { TableScroll } from '@/components/ui/TableScroll';
import {
  AlertState,
  FinishSelect,
  MarketValue,
  NoteInput,
  QTY_MAX,
  QTY_MIN,
  useLineSaver,
  useOwnedTexts,
  usePrintingLabel,
  useRemoveLine,
} from './lineParts';
import styles from './Lines.module.css';

const imageCard = (card: CardMini) => ({ ...card, energy: null, might: null });

type LineProps = {
  line: WishlistLine;
  offline: boolean;
  onMove: (line: WishlistLine) => void;
};

/** One wanted card on a phone (F3-j): what it is, its prices, what the user owns, its edits. */
export function LineCard({ line, offline, onMove }: LineProps) {
  const { t } = useTranslation('wishlists');
  const save = useLineSaver(line);
  const remove = useRemoveLine();
  const printing = usePrintingLabel();
  const owned = useOwnedTexts()(line);

  return (
    <article className={styles.card}>
      <div className={styles.art}>
        {line.card && <CardImage card={imageCard(line.card)} size="thumb" decorative />}
      </div>
      <div className={styles.body}>
        <h3 className={styles.name}>{line.name}</h3>
        <p className={styles.meta}>
          <span>{printing(line)}</span>
          <FinishSelect
            className={styles.finish}
            line={line}
            label={t('line.finish.label')}
            disabled={offline}
            save={save}
          />
        </p>
        <p className={styles.prices}>
          <span className={styles.label}>{`${t('line.market')}:`}</span>
          <MarketValue line={line} />
          <AlertState line={line} />
        </p>
        <p className={styles.owned} data-zero={owned.thisZero ? '' : undefined}>
          {owned.thisText}
        </p>
        {owned.showOther && (
          <p
            className={styles.owned}
            data-zero={owned.otherZero ? '' : undefined}
            title={t('line.otherHint')}
          >
            {owned.otherText}
          </p>
        )}
      </div>
      <div className={styles.controls}>
        <Stepper
          label={t('line.wanted')}
          value={line.qty}
          min={QTY_MIN}
          max={QTY_MAX}
          disabled={offline}
          onCommit={(qty) => void save({ qty })}
        />
        <MoneyField
          label={t('line.maxPrice')}
          value={line.max_price}
          disabled={offline}
          onCommit={(max_price) => {
            if (max_price !== line.max_price) void save({ max_price });
          }}
        />
        <div className={styles.note}>
          <Field label={t('line.note')}>
            {(control) => (
              <NoteInput
                id={control.id}
                line={line}
                disabled={offline}
                onSave={(note) => void save({ note })}
              />
            )}
          </Field>
        </div>
      </div>
      <div className={styles.actions}>
        <Button
          variant="ghost"
          size="sm"
          disabled={offline}
          aria-haspopup="dialog"
          onClick={() => onMove(line)}
        >
          {t('line.moveCopy')}
        </Button>
        <Button variant="danger" size="sm" disabled={offline} onClick={() => void remove(line)}>
          {t('line.remove')}
        </Button>
      </div>
    </article>
  );
}

/** The phone list of lines. */
export function LineCards({
  lines,
  listName,
  busy,
  offline,
  onMove,
}: {
  lines: WishlistLine[];
  listName: string;
  busy: boolean;
  offline: boolean;
  onMove: (line: WishlistLine) => void;
}) {
  const { t } = useTranslation('wishlists');
  return (
    <ul
      className={styles.cards}
      aria-label={t('lines', { name: listName })}
      aria-busy={busy || undefined}
    >
      {lines.map((line) => (
        <li key={line.id}>
          <LineCard line={line} offline={offline} onMove={onMove} />
        </li>
      ))}
    </ul>
  );
}

/** A compact quantity for the table: minus, the number, plus. */
function QtyCell({
  label,
  value,
  disabled,
  onCommit,
}: {
  label: string;
  value: number;
  disabled: boolean;
  onCommit: (next: number) => void;
}) {
  const { t } = useTranslation('collection');
  return (
    <span className={styles.qty}>
      <button
        type="button"
        className={styles.step}
        aria-label={`${t('line.fewer')}: ${label}`}
        disabled={disabled || value <= QTY_MIN}
        onClick={() => onCommit(value - 1)}
      >
        −
      </button>
      <DebouncedInput
        type="number"
        inputMode="numeric"
        className={styles.number}
        aria-label={label}
        min={QTY_MIN}
        max={QTY_MAX}
        disabled={disabled}
        value={String(value)}
        delay={500}
        onCommit={(next) => {
          const parsed = Number(next);
          if (next !== '' && Number.isInteger(parsed) && parsed >= QTY_MIN && parsed <= QTY_MAX) {
            onCommit(parsed);
          }
        }}
      />
      <button
        type="button"
        className={styles.step}
        aria-label={`${t('line.more')}: ${label}`}
        disabled={disabled || value >= QTY_MAX}
        onClick={() => onCommit(value + 1)}
      >
        +
      </button>
    </span>
  );
}

function Row({ line, offline, onMove }: LineProps) {
  const { t } = useTranslation('wishlists');
  const save = useLineSaver(line);
  const remove = useRemoveLine();
  const printing = usePrintingLabel();
  const owned = useOwnedTexts()(line);
  const { name } = line;

  return (
    <tr>
      <td>
        <span className={styles.cardCell}>
          <span className={styles.thumb}>
            {line.card && <CardImage card={imageCard(line.card)} size="thumb" decorative />}
          </span>
          <span className={styles.cardText}>
            <span className={styles.rowName}>{name}</span>
            <span className={styles.meta}>
              <span>{printing(line)}</span>
              <FinishSelect
                className={styles.finish}
                line={line}
                label={t('line.finishOf', { name })}
                disabled={offline}
                save={save}
              />
            </span>
          </span>
        </span>
      </td>
      <td>
        <QtyCell
          label={t('line.wantedOf', { name })}
          value={line.qty}
          disabled={offline}
          onCommit={(qty) => void save({ qty })}
        />
      </td>
      <td>
        <span className={styles.priceCell}>
          <DebouncedInput
            type="number"
            inputMode="decimal"
            className={styles.money}
            aria-label={t('line.maxPriceOf', { name })}
            min={0}
            step="0.01"
            disabled={offline}
            value={line.max_price === null ? '' : String(line.max_price)}
            delay={500}
            onCommit={(next) => {
              const parsed = next === '' ? null : Number(next);
              if (parsed !== null && !(Number.isFinite(parsed) && parsed >= 0)) return;
              if (parsed !== line.max_price) void save({ max_price: parsed });
            }}
          />
          <AlertState line={line} />
        </span>
      </td>
      <td className={styles.numeric}>
        <MarketValue line={line} />
      </td>
      <td className={styles.numeric} data-zero={owned.thisZero ? '' : undefined}>
        {owned.thisCount}
      </td>
      <td
        className={styles.numeric}
        data-zero={owned.otherZero ? '' : undefined}
        title={owned.showOther ? t('line.otherHint') : undefined}
      >
        {owned.showOther ? owned.otherCount : '—'}
      </td>
      <td>
        <NoteInput
          className={styles.noteInput}
          line={line}
          label={t('line.noteOf', { name })}
          disabled={offline}
          onSave={(note) => void save({ note })}
        />
      </td>
      <td>
        <span className={styles.rowActions}>
          <Button
            variant="ghost"
            size="sm"
            aria-label={t('line.moveCopyOf', { name })}
            title={t('line.moveCopyOf', { name })}
            aria-haspopup="dialog"
            disabled={offline}
            onClick={() => onMove(line)}
          >
            <Icon name="copy" size={16} />
          </Button>
          <Button
            variant="danger"
            size="sm"
            aria-label={t('line.removeOf', { name })}
            title={t('line.removeOf', { name })}
            disabled={offline}
            onClick={() => void remove(line)}
          >
            <Icon name="trash" size={16} />
          </Button>
        </span>
      </td>
    </tr>
  );
}

const COLUMNS = [
  'card',
  'wanted',
  'maxPrice',
  'market',
  'thisVersion',
  'otherVersions',
  'note',
  'actions',
] as const;
const NUMERIC = new Set<string>(['market', 'thisVersion', 'otherVersions']);

/** The lines as a table from 1240 px (F3-j), inline edits in every row. */
export function LinesTable({
  lines,
  listName,
  busy,
  offline,
  onMove,
}: {
  lines: WishlistLine[];
  listName: string;
  busy: boolean;
  offline: boolean;
  onMove: (line: WishlistLine) => void;
}) {
  const { t } = useTranslation('wishlists');
  return (
    <TableScroll fit>
      <table className={styles.table} aria-busy={busy || undefined}>
        <caption className="sr-only">{t('lines', { name: listName })}</caption>
        <thead>
          <tr>
            {COLUMNS.map((key) => (
              <th
                key={key}
                scope="col"
                className={NUMERIC.has(key) ? styles.numeric : undefined}
                title={key === 'otherVersions' ? t('line.otherHint') : undefined}
              >
                {t(`columns.${key}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <Row key={line.id} line={line} offline={offline} onMove={onMove} />
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}
