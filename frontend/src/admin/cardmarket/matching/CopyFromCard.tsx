import { useId, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { listAdminCards, type AdminCard } from '@/api/endpoints';
import { DebouncedInput, useGameMeta } from '@/catalog';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { cardRef } from './format';
import { CandidateImage } from './parts';
import styles from './MatchingPage.module.css';

/** How many cards the list shows; more asks to refine the search. */
export const SHOWN_CARDS = 8;

/** The card the form was filled from. */
export type CopiedFrom = { ref: string; name: string };

type CopyFromCardProps = {
  /** The first search: the card name of the Cardmarket product (a rune finds its siblings). */
  initialQuery: string;
  /** The sets of the Set filter, as the form's set select orders them. */
  sets: { id: string; name: string }[];
  /** No writes (offline, a create in flight, the card created). */
  disabled: boolean;
  copied: CopiedFrom | null;
  onUse: (card: AdminCard) => void;
  onClear: () => void;
};

/**
 * "Copy from an existing card" (CM-i): search the catalog (`GET /admin/cards`: a name or a
 * `SET-ID` code, a set, a type) and fill the create form from the card chosen.
 */
export function CopyFromCard({
  initialQuery,
  sets,
  disabled,
  copied,
  onUse,
  onClear,
}: CopyFromCardProps) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const titleId = useId();
  const hintId = useId();
  const meta = useGameMeta();
  const [q, setQ] = useState(initialQuery.trim());
  const [set, setSet] = useState('');
  const [type, setType] = useState('');
  const active = q !== '' || set !== '' || type !== '';
  const query = useQuery({
    queryKey: ['admin', 'cards', 'copy', q, set, type],
    queryFn: ({ signal }) => {
      const params: Record<string, string> = { per_page: '50' };
      if (q) params.q = q;
      if (set) params.set = set;
      if (type) params.type = type;
      return listAdminCards(params, signal);
    },
    enabled: active,
    placeholderData: keepPreviousData,
  });

  let results;
  if (!active) {
    results = <p className={styles.muted}>{t('matching.create.copy.empty')}</p>;
  } else if (query.isPending) {
    results = <Skeleton label={t('matching.create.copy.results')} lines={3} />;
  } else if (query.isError) {
    results = (
      <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
    );
  } else if (query.data.items.length === 0) {
    results = <p className={styles.muted}>{t('matching.create.copy.noCards')}</p>;
  } else {
    const { items, meta: page } = query.data;
    results = (
      <>
        <ul aria-label={t('matching.create.copy.results')} className={styles.candidates}>
          {items.slice(0, SHOWN_CARDS).map((card) => {
            const ref = cardRef(card.set_id, card.card_id);
            return (
              <li key={card.key} className={styles.candidate}>
                <CandidateImage card={card} />
                <div className={styles.candidateBody}>
                  <strong>{card.name}</strong>
                  <span>{ref}</span>
                  <span className={styles.muted}>
                    {[card.rarity, card.type].filter(Boolean).join(' · ')}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={disabled}
                    aria-label={t('matching.create.copy.useFor', { ref, name: card.name })}
                    onClick={() => onUse(card)}
                  >
                    {t('matching.create.copy.use')}
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
        {page.total > SHOWN_CARDS && (
          <p className={styles.muted}>
            {t('matching.create.copy.more', { shown: SHOWN_CARDS, total: page.total })}
          </p>
        )}
      </>
    );
  }

  return (
    <section aria-labelledby={titleId} className={styles.section}>
      <h3 id={titleId} className={styles.sectionTitle}>
        {t('matching.create.copy.title')}
      </h3>
      <p className={styles.help}>{t('matching.create.copy.intro')}</p>
      <div className={styles.filters}>
        <label className={styles.filterField}>
          {t('matching.create.copy.search')}
          <DebouncedInput
            aria-label={t('matching.create.copy.search')}
            aria-describedby={hintId}
            value={q}
            onCommit={(next) => setQ(next.trim())}
            // the section lives in the create form: Enter searches, it never creates the card
            onKeyDown={(event) => {
              if (event.key === 'Enter') event.preventDefault();
            }}
          />
          <span id={hintId}>{t('matching.create.copy.searchHint')}</span>
        </label>
        <label className={styles.filterField}>
          {t('matching.create.copy.set')}
          <Select
            aria-label={t('matching.create.copy.set')}
            value={set}
            onChange={(event) => setSet(event.target.value)}
          >
            <option value="">{t('matching.create.copy.anySet')}</option>
            {sets.map((one) => (
              <option key={one.id} value={one.id}>
                {t('matching.create.setOption', { id: one.id, name: one.name })}
              </option>
            ))}
          </Select>
        </label>
        <label className={styles.filterField}>
          {t('matching.create.copy.type')}
          <Select
            aria-label={t('matching.create.copy.type')}
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            <option value="">{t('matching.create.copy.anyType')}</option>
            {(meta.data?.types ?? []).map((one) => (
              <option key={one} value={one}>
                {one}
              </option>
            ))}
          </Select>
        </label>
      </div>
      <p role="status" className={styles.current}>
        {copied ? t('matching.create.copy.copied', { ref: copied.ref, name: copied.name }) : null}
      </p>
      {copied && (
        <div className={styles.rowActions}>
          <Button size="sm" variant="ghost" disabled={disabled} onClick={onClear}>
            {t('matching.create.copy.clear')}
          </Button>
        </div>
      )}
      {results}
    </section>
  );
}
