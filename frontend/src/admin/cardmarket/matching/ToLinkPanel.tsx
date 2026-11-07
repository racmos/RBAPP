import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import {
  createCardmarketLink,
  ignoreCardmarketProduct,
  type CardmarketLinkTarget,
  type CardmarketSuggestion,
  type CardmarketUnmatched,
} from '@/api/endpoints';
import { DebouncedInput } from '@/catalog';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Pagination } from '@/components/ui/Pagination';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { formatDate, formatMoney } from '@/lib/format';
import { apiQuery, scoreText, suggestionFoil } from './format';
import type { PanelProps } from './MatchingPage';
import { useLinkErrorText, useSlotLabel } from './parts';
import { useUndoToasts, useUnmatched } from './queries';
import styles from './MatchingPage.module.css';

/** "To link": the unmatched products of the latest load with their suggestions (CM-b). */
export function ToLinkPanel({ params, setParam, setPage, offline, openDialog }: PanelProps) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const query = useUnmatched(apiQuery('link', params));
  const toasts = useUndoToasts();
  const linkError = useLinkErrorText();

  const link = useMutation({
    mutationFn: ({
      product,
      target,
    }: {
      product: CardmarketUnmatched;
      target: CardmarketLinkTarget;
    }) => createCardmarketLink(product.id_product, target),
    onSuccess: (created, { product }) => toasts.linked(product.name, created),
    onError: (error: unknown, { target }) =>
      pushToast({
        kind: 'error',
        message: linkError(error, { ...target.card, foil: target.foil }),
      }),
  });
  const ignore = useMutation({
    mutationFn: (product: CardmarketUnmatched) =>
      ignoreCardmarketProduct(product.id_product, product.name),
    onSuccess: (_result, product) => toasts.ignored(product.id_product, product.name),
    onError: (error: unknown) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
  });
  const busy = offline || link.isPending || ignore.isPending;

  const filters = (
    <div className={styles.filters}>
      <label className={styles.filterField}>
        {t('matching.toLink.search')}
        <DebouncedInput
          aria-label={t('matching.toLink.search')}
          value={params.get('q') ?? ''}
          onCommit={(next) => setParam('q', next.trim() || null)}
        />
      </label>
      <label className={styles.filterField}>
        {t('matching.toLink.type')}
        <Select
          aria-label={t('matching.toLink.type')}
          value={params.get('type') ?? ''}
          onChange={(event) => setParam('type', event.target.value || null)}
        >
          <option value="">{t('matching.toLink.typeAll')}</option>
          <option value="single">{t('matching.toLink.typeSingle')}</option>
          <option value="nonsingle">{t('matching.toLink.typeSealed')}</option>
        </Select>
      </label>
    </div>
  );

  let body;
  if (query.isPending) {
    body = <Skeleton label={t('matching.toLink.caption')} lines={6} />;
  } else if (query.isError) {
    body = <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />;
  } else if (query.data.items.length === 0) {
    body = (
      <EmptyState title={t('matching.toLink.emptyTitle')} body={t('matching.toLink.emptyBody')} />
    );
  } else {
    const { items, meta } = query.data;
    body = (
      <>
        <p className={styles.meta}>
          <span>{t('matching.toLink.count', { count: meta.total })}</span>
          {meta.date && <span>{t('matching.toLink.latest', { date: formatDate(meta.date) })}</span>}
        </p>
        <ul aria-label={t('matching.toLink.caption')} className={styles.rows}>
          {items.map((product) => (
            <ProductRow
              key={product.id_product}
              product={product}
              busy={busy}
              onLink={(target) => link.mutate({ product, target })}
              onChoose={() => openDialog({ id_product: product.id_product, name: product.name })}
              onCreate={() =>
                openDialog({
                  id_product: product.id_product,
                  name: product.name,
                  mode: 'create',
                  facts: { category: product.category, expansion: product.expansion },
                })
              }
              onIgnore={() => ignore.mutate(product)}
            />
          ))}
        </ul>
        {meta.pages > 1 && <Pagination page={meta.page} pages={meta.pages} onChange={setPage} />}
      </>
    );
  }

  return (
    <>
      {filters}
      {body}
    </>
  );
}

function ProductRow({
  product,
  busy,
  onLink,
  onChoose,
  onCreate,
  onIgnore,
}: {
  product: CardmarketUnmatched;
  busy: boolean;
  onLink: (target: CardmarketLinkTarget) => void;
  onChoose: () => void;
  onCreate: () => void;
  onIgnore: () => void;
}) {
  const { t } = useTranslation('admin');
  const identity = product.suggestions.find((one) => one.kind === 'product');
  const cards = product.suggestions.filter((one) => one.kind === 'card');
  const single = product.type === 'single';
  return (
    <li className={styles.row}>
      <div className={styles.rowHead}>
        <h3 className={styles.rowTitle}>{product.name}</h3>
        <span className={styles.muted}>
          {[
            `#${product.id_product}`,
            t(single ? 'matching.single' : 'matching.sealed'),
            product.category,
            product.expansion?.name ?? '—',
            product.low_price === null ? '—' : formatMoney(product.low_price),
            product.first_seen_date
              ? t('matching.toLink.firstSeen', { date: formatDate(product.first_seen_date) })
              : null,
          ]
            .filter(Boolean)
            .join(' · ')}
        </span>
      </div>
      {identity ? (
        <p className={styles.identity}>
          <Badge tone="success">{t('matching.toLink.identity')}</Badge>
          <span className={styles.muted}>
            {t('matching.toLink.identityHint')} {t('matching.toLink.identityEdit')}{' '}
            <Link to="/admin/products">{t('matching.toLink.identityProducts')}</Link>.
          </span>
        </p>
      ) : (
        <>
          <div className={styles.suggestions}>
            {cards.length === 0 && single && (
              <span className={styles.muted}>{t('matching.toLink.noSuggestions')}</span>
            )}
            {!single && cards.length === 0 && (
              <span className={styles.muted}>{t('matching.toLink.noProduct')}</span>
            )}
            {cards.map((suggestion) => (
              <SuggestionButton
                key={String(suggestion.id)}
                suggestion={suggestion}
                busy={busy}
                onLink={onLink}
              />
            ))}
          </div>
          <div className={styles.rowActions}>
            {single && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                aria-label={t('matching.toLink.chooseFor', { name: product.name })}
                onClick={onChoose}
              >
                {t('matching.toLink.choose')}
              </Button>
            )}
            {single && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                aria-label={t('matching.toLink.createFor', { name: product.name })}
                onClick={onCreate}
              >
                {t('matching.toLink.create')}
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              aria-label={t('matching.toLink.ignoreFor', { name: product.name })}
              onClick={onIgnore}
            >
              {t('matching.toLink.ignore')}
            </Button>
          </div>
        </>
      )}
    </li>
  );
}

function SuggestionButton({
  suggestion,
  busy,
  onLink,
}: {
  suggestion: CardmarketSuggestion;
  busy: boolean;
  onLink: (target: CardmarketLinkTarget) => void;
}) {
  const { t } = useTranslation('admin');
  const slotLabel = useSlotLabel();
  const foil = suggestionFoil(suggestion.free_foils);
  const ref = String(suggestion.id);
  const values = { ref, name: suggestion.name, score: scoreText(suggestion.score) };
  const label =
    foil === undefined || foil === null
      ? t('matching.toLink.suggestion', values)
      : t('matching.toLink.suggestionSlot', { ...values, slot: slotLabel(foil) });
  return (
    <Button
      size="sm"
      variant="ghost"
      className={styles.suggestion}
      disabled={busy || foil === undefined || !suggestion.set || !suggestion.number}
      title={foil === undefined ? t('matching.toLink.slotsTaken') : undefined}
      onClick={() => {
        if (foil === undefined || !suggestion.set || !suggestion.number) return;
        onLink({ card: { set_id: suggestion.set, card_id: suggestion.number }, foil });
      }}
    >
      {label}
    </Button>
  );
}
