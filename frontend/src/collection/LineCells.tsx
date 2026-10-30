import { useTranslation } from 'react-i18next';
import { DebouncedInput } from '@/catalog';
import type { CollectionLine } from '@/api/types';
import { Select } from '@/components/ui/Select';
import { useEnumLabel } from '@/i18n';
import { useLineSaver } from './useLineSaver';
import styles from './CollectionTable.module.css';

type LineCellsProps = {
  line: CollectionLine;
  /** `{{name}}, line 2`, so every control has its own name. */
  who: string;
  conditions: string[];
  languages: string[];
  disabled: boolean;
};

function Whole({
  label,
  value,
  min,
  max,
  disabled,
  onCommit,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  disabled: boolean;
  onCommit: (next: number) => void;
}) {
  return (
    <DebouncedInput
      type="number"
      inputMode="numeric"
      className={styles.number}
      aria-label={label}
      min={min}
      max={max}
      disabled={disabled}
      value={String(value)}
      delay={500}
      onCommit={(next) => {
        const parsed = Number(next);
        if (next !== '' && Number.isInteger(parsed) && parsed >= min && parsed <= max) {
          onCommit(parsed);
        }
      }}
    />
  );
}

function Euro({
  label,
  value,
  disabled,
  onCommit,
}: {
  label: string;
  value: number | null;
  disabled: boolean;
  onCommit: (next: number | null) => void;
}) {
  return (
    <DebouncedInput
      type="number"
      inputMode="decimal"
      className={styles.money}
      aria-label={label}
      min={0}
      step="0.01"
      disabled={disabled}
      value={value === null ? '' : String(value)}
      delay={500}
      onCommit={(next) => {
        if (next === '') return onCommit(null);
        const parsed = Number(next);
        if (Number.isFinite(parsed) && parsed >= 0) onCommit(parsed);
      }}
    />
  );
}

/** Cardmarket language names (the API values) as the short codes the table shows. */
const LANGUAGE_CODES: Record<string, string> = {
  English: 'EN',
  French: 'FR',
  German: 'DE',
  Spanish: 'ES',
  Italian: 'IT',
  'Simplified Chinese': 'ZH',
  'Traditional Chinese': 'ZH-TW',
  Japanese: 'JA',
  Portuguese: 'PT',
  Russian: 'RU',
  Korean: 'KO',
};

const codeOf = (kind: 'condition' | 'language', value: string) =>
  kind === 'condition' ? value : (LANGUAGE_CODES[value] ?? value.slice(0, 2).toUpperCase());

/**
 * Compact for the table (owner feedback S24 q): the empty value shows "—", a condition its code
 * ("NM") and a language its code ("FR"); the full names stay in the option text (the accessible
 * name) and in the `title` tooltip.
 */
function Choice({
  kind,
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  kind: 'condition' | 'language';
  label: string;
  value: string | null;
  options: string[];
  disabled: boolean;
  onChange: (next: string | null) => void;
}) {
  const { t } = useTranslation('collection');
  const { label: enumLabel } = useEnumLabel();
  const listed = value !== null && !options.includes(value) ? [value, ...options] : options;
  return (
    <Select
      className={styles.code}
      title={value === null ? t('line.noValue') : enumLabel(kind, value)}
      aria-label={label}
      value={value ?? ''}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value === '' ? null : event.target.value)}
    >
      <option value="" label="—" title={t('line.noValue')}>
        {t('line.noValue')}
      </option>
      {listed.map((option) => (
        <option
          key={option}
          value={option}
          label={codeOf(kind, option)}
          title={enumLabel(kind, option)}
        >
          {enumLabel(kind, option)}
        </option>
      ))}
    </Select>
  );
}

/**
 * The seven editable cells of a line: copies, to sell, on sale, sale price, condition, language,
 * purchase price (F3-h S3). Each change is saved like in the line sheet of F3-g.
 */
export function LineCells({ line, who, conditions, languages, disabled }: LineCellsProps) {
  const { t } = useTranslation('collection');
  const save = useLineSaver(line);
  const column = (key: string) => `${t(`table.columns.${key}` as 'table.columns.qty')}: ${who}`;
  return (
    <>
      <td className={styles.numeric}>
        <Whole
          label={column('qty')}
          value={line.qty}
          min={1}
          max={9999}
          disabled={disabled}
          onCommit={(qty) => void save({ qty })}
        />
      </td>
      <td className={styles.numeric}>
        <Whole
          label={column('sellQty')}
          value={line.sell_qty}
          min={0}
          max={line.qty}
          disabled={disabled}
          onCommit={(sell_qty) => void save({ sell_qty })}
        />
      </td>
      <td>
        <button
          type="button"
          role="switch"
          aria-checked={line.selling}
          aria-label={column('selling')}
          className={styles.switch}
          disabled={disabled}
          onClick={() => void save({ selling: !line.selling })}
        >
          <span aria-hidden="true" />
        </button>
      </td>
      <td className={styles.numeric}>
        <Euro
          label={column('sellPrice')}
          value={line.sell_price}
          disabled={disabled}
          onCommit={(sell_price) => void save({ sell_price })}
        />
      </td>
      <td>
        <Choice
          kind="condition"
          label={column('condition')}
          value={line.condition}
          options={conditions}
          disabled={disabled}
          onChange={(condition) => void save({ condition })}
        />
      </td>
      <td>
        <Choice
          kind="language"
          label={column('language')}
          value={line.language}
          options={languages}
          disabled={disabled}
          onChange={(language) => void save({ language })}
        />
      </td>
      <td className={styles.numeric}>
        <Euro
          label={column('purchase')}
          value={line.purchase_price}
          disabled={disabled}
          onCommit={(purchase_price) => void save({ purchase_price })}
        />
      </td>
    </>
  );
}
