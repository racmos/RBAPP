import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type Ref } from 'react';
import { useTranslation } from 'react-i18next';
import type { CardListParams, CardSummary } from '@/api/types';
import { useOffline } from '@/auth';
import { CardImage, DomainPips } from '@/components/card';
import { useEnumLabel } from '@/i18n';
import { formatMoney } from '@/lib/format';
import { COMBOBOX_LIMIT, useCardSearch } from './queries';
import styles from './CardCombobox.module.css';

const MIN_CHARS = 2;
const DEBOUNCE_MS = 250;

export type CardComboboxProps = {
  /** Accessible name of the input; shown above it unless `hideLabel`. */
  label: string;
  hideLabel?: boolean;
  onSelect: (card: CardSummary) => void;
  /** Called after `onSelect` when the card was picked with Enter (the quick add acts on it). */
  onEnterSelect?: (card: CardSummary) => void;
  /** Extra `GET /cards` params, for example `{ base_only: true, exclude_supertype: ['Token'] }`. */
  filters?: Partial<CardListParams>;
  placeholder?: string;
  autoFocus?: boolean;
  /** Empty the input after a selection (default) or leave the card name in it. */
  clearOnSelect?: boolean;
  id?: string;
  className?: string;
  inputRef?: Ref<HTMLInputElement>;
};

const NO_FILTERS: Partial<CardListParams> = {};

const fold = (value: string) =>
  value.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase().trim();

/**
 * The search also matches ability text and tags, so a card can come first without its name
 * matching (owner feedback S18 d). Exact names first, then names that start with the query, then
 * names that contain it, then the rest; each group keeps the API order.
 */
function rankByName(items: readonly CardSummary[], query: string): CardSummary[] {
  const needle = fold(query);
  if (!needle) return [...items];
  const rank = (card: CardSummary) => {
    const name = fold(card.name);
    if (name === needle) return 0;
    if (name.startsWith(needle)) return 1;
    return name.includes(needle) ? 2 : 3;
  };
  return items
    .map((card, index) => ({ card, index, rank: rank(card) }))
    .sort((a, b) => a.rank - b.rank || a.index - b.index)
    .map(({ card }) => card);
}

/**
 * Card picker that searches the server as you type (F2-k). ARIA 1.2 editable combobox with list
 * autocomplete: focus stays in the input and `aria-activedescendant` names the active option.
 */
export function CardCombobox({
  label,
  hideLabel,
  onSelect,
  onEnterSelect,
  filters = NO_FILTERS,
  placeholder,
  autoFocus,
  clearOnSelect = true,
  id,
  className,
  inputRef,
}: CardComboboxProps) {
  const { t } = useTranslation('cards');
  const { typeLabel } = useEnumLabel();
  const offline = useOffline();
  const generated = useId();
  const inputId = id ?? `${generated}-input`;
  const listId = `${generated}-list`;
  const root = useRef<HTMLDivElement>(null);

  const [text, setText] = useState('');
  const [debounced, setDebounced] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  // A real effect instead of the `autoFocus` attribute: the picker opens in sheets and dialogs.
  useEffect(() => {
    if (autoFocus) root.current?.querySelector('input')?.focus();
  }, [autoFocus]);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(text), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text]);

  const query = text.trim();
  const ready = query.length >= MIN_CHARS;
  const settled = debounced.trim();
  const search = useCardSearch(filters, settled, ready && settled.length >= MIN_CHARS && !offline);

  const found = search.data?.data.items;
  const items = useMemo(
    () => (ready && found ? rankByName(found, settled) : []),
    [ready, found, settled],
  );
  const total = search.data?.meta?.total ?? items.length;
  const visible = open && ready;
  const listed = visible && items.length > 0;
  const activeIndex = items.length > 0 ? Math.min(active, items.length - 1) : -1;
  const optionId = (index: number) => `${listId}-option-${index}`;

  let state: 'loading' | 'empty' | 'error' | 'offline' | null = null;
  if (ready && !search.data) {
    if (offline) state = 'offline';
    else if (search.isError) state = 'error';
    else state = 'loading';
  } else if (ready && items.length === 0) {
    state = 'empty';
  }
  const stateText = state ? t(`combobox.${state}`, { query }) : '';

  const activeCard = activeIndex >= 0 ? items[activeIndex] : undefined;
  let announcement = '';
  if (visible) {
    announcement = state
      ? stateText
      : `${t('combobox.results', { count: total })}. ${activeCard?.name ?? ''}`;
  }

  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const choose = (card: CardSummary) => {
    onSelect(card);
    setText(clearOnSelect ? '' : card.name);
    setOpen(false);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    const count = items.length;
    switch (event.key) {
      case 'ArrowDown':
        if (!visible && ready) {
          event.preventDefault();
          setOpen(true);
        } else if (listed) {
          event.preventDefault();
          setActive((activeIndex + 1) % count);
        }
        break;
      case 'ArrowUp':
        if (listed) {
          event.preventDefault();
          setActive((activeIndex - 1 + count) % count);
        }
        break;
      case 'Home':
      case 'End':
        if (listed) {
          event.preventDefault();
          setActive(event.key === 'Home' ? 0 : count - 1);
        }
        break;
      case 'Enter':
        if (listed && activeCard) {
          event.preventDefault();
          choose(activeCard);
          onEnterSelect?.(activeCard);
        }
        break;
      case 'Escape':
        if (visible) {
          event.preventDefault();
          event.stopPropagation();
          setOpen(false);
        } else if (text !== '') {
          event.preventDefault();
          event.stopPropagation();
          setText('');
        }
        break;
      case 'Tab':
        setOpen(false);
        break;
      default:
        break;
    }
  };

  return (
    <div
      ref={root}
      className={[styles.root, className].filter(Boolean).join(' ')}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <label htmlFor={inputId} className={hideLabel ? 'sr-only' : styles.label}>
        {label}
      </label>
      <input
        id={inputId}
        ref={inputRef}
        type="text"
        role="combobox"
        className={styles.input}
        value={text}
        placeholder={placeholder}
        autoComplete="off"
        autoCapitalize="off"
        spellCheck={false}
        aria-expanded={listed}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={listed && activeIndex >= 0 ? optionId(activeIndex) : undefined}
        onChange={(event) => {
          setText(event.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
      />

      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>

      {visible && (
        <div className={styles.popup}>
          {listed ? (
            <ul id={listId} role="listbox" aria-label={label} className={styles.list}>
              {items.map((card, index) => (
                <li
                  key={card.key}
                  id={optionId(index)}
                  role="option"
                  aria-selected={index === activeIndex}
                  data-active={index === activeIndex || undefined}
                  className={styles.option}
                  onPointerDown={(event) => {
                    event.preventDefault(); // keep the focus in the input
                    choose(card);
                  }}
                >
                  <CardImage card={card} size="thumb" decorative className={styles.thumb} />
                  <span className={styles.body}>
                    <span className={styles.name}>{card.name}</span>
                    <span className={styles.meta}>
                      <span>
                        {card.set_id} · #{card.card_id}
                      </span>
                      <span>{typeLabel(card.supertype, card.type)}</span>
                      <DomainPips domains={card.domains} size={14} />
                    </span>
                  </span>
                  <span className={styles.price}>
                    {card.price?.market != null ? formatMoney(card.price.market) : '—'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div id={listId} aria-hidden="true" className={styles.state} data-state={state}>
              {stateText}
            </div>
          )}
          {listed && total > COMBOBOX_LIMIT && (
            <div aria-hidden="true" className={styles.more}>
              {t('combobox.more', { count: total - items.length })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
