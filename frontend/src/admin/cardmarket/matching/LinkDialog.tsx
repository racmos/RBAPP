import { useEffect, useId, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  createCardmarketLink,
  relinkCardmarketLink,
  type CardmarketCandidateCard,
  type CardmarketExpansion,
  type CardmarketFoil,
  type CardmarketLink,
  type CardmarketLinkTarget,
} from '@/api/endpoints';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { CreateCardForm } from './CreateCardForm';
import { MAX_QUERY, cardRef, defaultFoil, firstQuery } from './format';
import { CandidateImage, linkConflict, useLinkErrorText, useSlotLabel, useSlotRef } from './parts';
import { useCandidates, useUndoToasts } from './queries';
import styles from './MatchingPage.module.css';

const SEARCH_DELAY_MS = 300;

/** What a list already knows of a Cardmarket item; the dialog fetches it otherwise. */
export type CardmarketItemFacts = {
  category: string | null;
  expansion: CardmarketExpansion | null;
};

export type LinkSubject = {
  id_product: number;
  name: string;
  /** The link to replace: the dialog relinks (PUT) instead of linking (POST). */
  current?: CardmarketLink;
  /** Open on the form that creates the card (CM-c) instead of the search. */
  mode?: 'search' | 'create';
  facts?: CardmarketItemFacts;
};

/** The search (with its first text) or the create-card form. */
type View = { mode: 'search'; q?: string } | { mode: 'create' };

type LinkDialogProps = {
  subject: LinkSubject | null;
  offline: boolean;
  onClose: () => void;
  /** Show the link of another Cardmarket product (the one holding a slot). */
  onOpenLink: (idProduct: number) => void;
};

/**
 * Choose the card (and slot) a Cardmarket product links to: search, images, Link (CM-b); or
 * create the missing card from the item and link it (CM-c).
 */
export function LinkDialog({ subject, offline, onClose, onOpenLink }: LinkDialogProps) {
  const { t } = useTranslation('admin');
  const [view, setView] = useState<View>({ mode: subject?.mode ?? 'search' });
  const [shown, setShown] = useState(subject);
  if (subject !== shown) {
    setShown(subject);
    setView({ mode: subject?.mode ?? 'search' });
  }
  let title = '';
  if (subject && view.mode === 'create') {
    title = t('matching.create.title', { name: subject.name });
  } else if (subject) {
    title = t(subject.current ? 'matching.dialog.relink' : 'matching.dialog.link', {
      name: subject.name,
    });
  }
  return (
    <Modal open={subject !== null} title={title} onClose={onClose} size="xl">
      {subject && view.mode === 'create' && (
        <CreateCardForm
          key={subject.id_product}
          subject={subject}
          offline={offline}
          onClose={onClose}
          onSearch={(q) => setView({ mode: 'search', q })}
        />
      )}
      {subject && view.mode === 'search' && (
        <LinkDialogBody
          key={`${subject.id_product}-${view.q ?? ''}`}
          subject={subject}
          firstText={view.q}
          offline={offline}
          onClose={onClose}
          onOpenLink={onOpenLink}
          onCreate={() => setView({ mode: 'create' })}
        />
      )}
    </Modal>
  );
}

type Failure = { error: unknown; target: CardmarketLinkTarget };

function LinkDialogBody({
  subject,
  firstText,
  offline,
  onClose,
  onOpenLink,
  onCreate,
}: LinkDialogProps & { subject: LinkSubject; firstText?: string; onCreate: () => void }) {
  const { t } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const slotRef = useSlotRef();
  const errorText = useLinkErrorText();
  const toasts = useUndoToasts();
  const [text, setText] = useState(() => firstText ?? firstQuery(subject.name));
  const [q, setQ] = useState(() => text.trim());
  const [failure, setFailure] = useState<Failure | null>(null);
  const query = useCandidates(subject.id_product, q);
  const relinking = subject.current !== undefined;

  useEffect(() => {
    const timer = setTimeout(() => setQ(text.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [text]);

  const write = useMutation({
    mutationFn: ({
      target,
      relink,
    }: {
      target: CardmarketLinkTarget;
      relink: boolean;
    }): Promise<{ link: CardmarketLink; previous: CardmarketLink | null }> =>
      relink
        ? relinkCardmarketLink(subject.id_product, target)
        : createCardmarketLink(subject.id_product, target).then((link) => ({
            link,
            previous: null,
          })),
    onSuccess: ({ link, previous }) => {
      onClose();
      if (previous) toasts.relinked(subject.name, link, previous);
      else toasts.linked(subject.name, link);
    },
    onError: (error: unknown, { target }) => setFailure({ error, target }),
  });

  const send = (target: CardmarketLinkTarget, relink = relinking) => {
    setFailure(null);
    write.mutate({ target, relink });
  };

  const product = query.data?.product;
  const current = subject.current ?? product?.link ?? null;
  const conflict = failure ? linkConflict(failure.error) : null;
  const shortQuery = text.trim().length === 1;

  let results;
  if (query.isPending && !query.data) {
    results = shortQuery ? null : <Skeleton label={t('matching.dialog.cards')} lines={4} />;
  } else if (query.isError) {
    results = (
      <ErrorState message={common('errorState.title')} onRetry={() => void query.refetch()} />
    );
  } else if (query.data && query.data.cards.length === 0) {
    results = <p className={styles.muted}>{t('matching.dialog.noCards')}</p>;
  } else if (query.data) {
    results = (
      <ul aria-label={t('matching.dialog.cards')} className={styles.candidates}>
        {query.data.cards.map((card) => (
          <CandidateRow
            key={`${card.set_id}-${card.card_id}`}
            card={card}
            relinking={relinking}
            disabled={offline || write.isPending}
            onLink={send}
          />
        ))}
      </ul>
    );
  }

  return (
    <div className={styles.dialog}>
      <p className={styles.muted}>
        {[`#${subject.id_product}`, product?.category, product?.expansion?.name]
          .filter(Boolean)
          .join(' · ')}
      </p>
      {current && (
        <p className={styles.current}>
          {t('matching.dialog.linkedNow', { target: slotRef(current) })}
        </p>
      )}
      <Field label={t('matching.dialog.search')} hint={t('matching.dialog.searchHint')}>
        {(control) => (
          <Input
            {...control}
            maxLength={MAX_QUERY}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        )}
      </Field>
      {shortQuery && <p className={styles.muted}>{t('matching.dialog.minChars')}</p>}
      {!relinking && (
        <p className={styles.identity}>
          <Button size="sm" variant="ghost" disabled={offline} onClick={onCreate}>
            {t('matching.create.open')}
          </Button>
          <span className={styles.muted}>{t('matching.create.openHint')}</span>
        </p>
      )}
      <p className={styles.help}>{t('matching.slotHelp')}</p>
      {failure && (
        <div role="alert" className={styles.alert}>
          <span>
            {errorText(failure.error, { ...failure.target.card, foil: failure.target.foil })}
          </span>
          {conflict?.field === 'card' && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                onClose();
                onOpenLink(conflict.linkedId);
              }}
            >
              {t('matching.dialog.openOther', { id: conflict.linkedId })}
            </Button>
          )}
          {conflict?.field === 'id_product' && (
            <Button
              size="sm"
              disabled={offline}
              pending={write.isPending}
              onClick={() => send(failure.target, true)}
            >
              {t('matching.dialog.relinkInstead')}
            </Button>
          )}
        </div>
      )}
      {results}
    </div>
  );
}

function CandidateRow({
  card,
  relinking,
  disabled,
  onLink,
}: {
  card: CardmarketCandidateCard;
  relinking: boolean;
  disabled: boolean;
  onLink: (target: CardmarketLinkTarget) => void;
}) {
  const { t } = useTranslation('admin');
  const slotLabel = useSlotLabel();
  const selectId = useId();
  const ref = cardRef(card.set_id, card.card_id);
  const [foil, setFoil] = useState<CardmarketFoil>(() =>
    defaultFoil(
      card,
      card.links.map((link) => link.foil),
    ),
  );
  return (
    <li className={styles.candidate}>
      <CandidateImage card={card} />
      <div className={styles.candidateBody}>
        <strong>{card.name}</strong>
        <span>{ref}</span>
        <span className={styles.muted}>{[card.rarity, card.type].filter(Boolean).join(' · ')}</span>
        {card.links.map((link) => (
          <Badge key={`${link.id_product}-${link.foil ?? ''}`} tone="warning">
            {t('matching.dialog.linkedBadge', { id: link.id_product, slot: slotLabel(link.foil) })}
          </Badge>
        ))}
        <span className={styles.candidateActions}>
          <Select
            id={selectId}
            aria-label={t('matching.dialog.slotFor', { ref })}
            value={foil ?? ''}
            onChange={(event) => {
              const value = event.target.value;
              setFoil(value === 'N' || value === 'S' ? value : null);
            }}
          >
            <option value="">{t('matching.slotOption.none')}</option>
            <option value="N">{t('matching.slotOption.N')}</option>
            <option value="S">{t('matching.slotOption.S')}</option>
          </Select>
          <Button
            size="sm"
            disabled={disabled}
            onClick={() => onLink({ card: { set_id: card.set_id, card_id: card.card_id }, foil })}
          >
            {t(relinking ? 'matching.dialog.relinkTo' : 'matching.dialog.linkTo', { ref })}
          </Button>
        </span>
      </div>
    </li>
  );
}
