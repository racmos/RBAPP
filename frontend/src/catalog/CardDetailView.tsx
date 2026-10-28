import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import type { CardDetail, CardMini } from '@/api/types';
import {
  AbilityText,
  BanBadge,
  CardImage,
  DomainPips,
  PriceTag,
  RarityDot,
} from '@/components/card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useDocumentTitle, useEnumLabel } from '@/i18n';
import { formatDate, formatMoney, type Lang } from '@/lib/format';
import { legacyHref } from '@/shell/legacyRoutes';
import { CardPriceHistory } from './CardPriceHistory';
import styles from './CardDetailView.module.css';

type CardImageCard = Parameters<typeof CardImage>[0]['card'];

export type CardDetailViewProps = {
  presentation: 'page' | 'modal';
  card: CardDetail | undefined;
  isPending?: boolean;
  isError?: boolean;
  error?: Error | null;
  onRetry?: () => void;
};

export function CardDetailView({
  presentation,
  card,
  isPending,
  isError,
  error,
  onRetry,
}: CardDetailViewProps) {
  const { t, i18n } = useTranslation('cards');
  const { label } = useEnumLabel();
  const lang = (i18n.language.split('-')[0] === 'en' ? 'en' : 'es') as Lang;

  useDocumentTitle(card?.name);

  if (isPending || (!card && !isError)) {
    return (
      <div className={styles.page} aria-busy="true" data-testid="card-detail-loading">
        <span className="sr-only">{t('detail.loading')}</span>
        <div className={styles.grid}>
          <Skeleton label={t('detail.loading')} lines={12} />
        </div>
      </div>
    );
  }

  if (isError || !card) {
    const is404 = error && 'status' in error && error.status === 404;
    if (is404) {
      return (
        <EmptyState
          icon="info"
          title={t('detail.notFound.title')}
          body={t('detail.notFound.body')}
          action={{ label: t('detail.notFound.action'), onAction: () => {} }}
        />
      );
    }
    return <ErrorState message={error?.message ?? t('detail.loading')} onRetry={onRetry} />;
  }

  const HeaderTag = presentation === 'page' ? 'h1' : 'h2';
  const totalCopies = card.my_lines.reduce((sum, line) => sum + line.qty, 0);

  return (
    <div className={styles.page}>
      <div className={styles.grid} data-presentation={presentation}>
        <div className={styles.columnA}>
          <div className={styles.imageWrap}>
            <CardImage card={card} size="full" priority decorative />
          </div>
          <PricesPanel card={card} lang={lang} />
          <CardPriceHistory
            setId={card.set_id}
            cardId={card.card_id}
            foilable={card.foilable}
            name={card.name}
          />
        </div>

        <div className={styles.columnB}>
          <header className={styles.header}>
            <p className={styles.eyebrow}>
              {t('detail.eyebrow', { set: card.set.name, number: card.card_id })}
            </p>
            <HeaderTag className={styles.name}>{card.name}</HeaderTag>
            <div className={styles.meta}>
              <RarityDot rarity={card.rarity} showLabel />
              <DomainPips domains={card.domains} size={18} />
              <span className={styles.typeLine}>
                {card.supertype
                  ? `${label('supertype', card.supertype)} · ${label('type', card.type)}`
                  : label('type', card.type)}
              </span>
            </div>
            {card.tags.length > 0 && (
              <div className={styles.tags}>
                {card.tags.map((tag) => (
                  <Link
                    key={tag}
                    className={styles.tag}
                    to={`/cards?tag=${encodeURIComponent(tag)}`}
                  >
                    {tag}
                  </Link>
                ))}
              </div>
            )}
          </header>

          <section aria-labelledby="bans-title" className={styles.panel}>
            <h2 id="bans-title" className={styles.sectionTitle}>
              <BanBadge bans={card.bans} />
            </h2>
            {card.ban_info.length === 0 ? (
              <p className={styles.muted}>{t('detail.bans.none')}</p>
            ) : (
              <ul className={styles.banList}>
                {card.ban_info.map((ban) => (
                  <li key={ban.mode}>
                    {t('detail.bans.line', {
                      mode: label('mode', ban.mode),
                      date: formatDate(ban.since, lang),
                    })}
                    {ban.reason && (
                      <span className={styles.banReason}>
                        {' '}
                        {t('detail.bans.reason', { reason: ban.reason })}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="text-title" className={styles.panel}>
            <h2 id="text-title" className={styles.sectionTitle}>
              {t('detail.text.title')}
            </h2>
            <AbilityText text={card.ability} />
          </section>

          <section aria-labelledby="attrs-title" className={styles.panel}>
            <h2 id="attrs-title" className={styles.sectionTitle}>
              {t('detail.attributes.title')}
            </h2>
            <dl className={styles.attrs}>
              <Attribute label={t('detail.attributes.energy')} value={card.energy} />
              <Attribute label={t('detail.attributes.power')} value={card.power} />
              <Attribute label={t('detail.attributes.might')} value={card.might} />
              <Attribute
                label={t('detail.attributes.type')}
                value={
                  card.supertype
                    ? `${label('supertype', card.supertype)} · ${label('type', card.type)}`
                    : label('type', card.type)
                }
              />
              <Attribute
                label={t('detail.attributes.rarity')}
                value={label('rarity', card.rarity)}
              />
              <Attribute
                label={t('detail.attributes.domains')}
                value={
                  card.domains.length > 0
                    ? card.domains.map((d) => label('domain', d)).join(' · ')
                    : null
                }
              />
              <Attribute label={t('detail.attributes.artist')} value={card.artist} />
            </dl>
          </section>

          <section aria-labelledby="mine-title" className={styles.panel}>
            <h2 id="mine-title" className={styles.sectionTitle}>
              {t('detail.mine.title')}
            </h2>
            {card.my_lines.length === 0 ? (
              <p className={styles.muted}>{t('detail.mine.none')}</p>
            ) : (
              <>
                <p className={styles.mineTotal}>{t('detail.mine.total', { count: totalCopies })}</p>
                <ul className={styles.lineList}>
                  {card.my_lines.map((line) => (
                    <li key={line.id} className={styles.line}>
                      {t('detail.mine.line', {
                        qty: line.qty,
                        condition: line.condition,
                        language: line.language,
                      })}
                      {line.foil && <span className={styles.foilBadge}>{t('foil')}</span>}
                      {line.selling && (
                        <span className={styles.selling}>
                          {line.sell_price !== null
                            ? t('detail.mine.selling', {
                                price: formatMoney(line.sell_price, lang),
                              })
                            : t('detail.mine.sellingNoPrice')}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <Link
                  to={{ pathname: '/collection', search: `?q=${card.set_id}-${card.card_id}` }}
                  className={styles.manageLink}
                >
                  {t('detail.mine.manage')}
                </Link>
              </>
            )}
          </section>
        </div>

        <div className={styles.columnC}>
          {card.printings.length > 1 && (
            <section aria-labelledby="printings-title" className={styles.panel}>
              <h2 id="printings-title" className={styles.sectionTitle}>
                {t('detail.printings.title')}
              </h2>
              <ul className={styles.printingList}>
                {card.printings.map((printing) => (
                  <PrintingItem
                    key={printing.key}
                    printing={printing}
                    current={printing.set_id === card.set_id && printing.card_id === card.card_id}
                    lang={lang}
                  />
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="related-title" className={styles.panel}>
            <h2 id="related-title" className={styles.sectionTitle}>
              {t('detail.related.title')}
            </h2>
            {card.related.length === 0 ? (
              <p className={styles.muted}>{t('detail.related.none')}</p>
            ) : (
              <ul className={styles.relatedGrid}>
                {card.related.slice(0, 12).map((related) => (
                  <li key={related.key}>
                    <Link
                      className={styles.relatedCard}
                      to={`/cards/${related.set_id}/${related.card_id}`}
                    >
                      <CardImage card={imageCardFromMini(related)} size="thumb" decorative />
                      <span className={styles.relatedName}>{related.name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="decks-title" className={styles.panel}>
            <h2 id="decks-title" className={styles.sectionTitle}>
              {t('detail.decks.title')}
            </h2>
            {card.in_decks.length === 0 ? (
              <p className={styles.muted}>{t('detail.decks.none')}</p>
            ) : (
              <ul className={styles.deckList}>
                {card.in_decks.map((deck) => (
                  <li key={deck.deck_id}>
                    <a
                      href={`${legacyHref('decks')}/view/${deck.deck_id}`}
                      className={styles.deckLink}
                    >
                      {deck.name} — {t('detail.decks.qty', { count: deck.qty })}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function Attribute({ label, value }: { label: string; value: string | number | null }) {
  const display = value ?? '—';
  return (
    <div className={styles.attr}>
      <dt className={styles.attrLabel}>{label}</dt>
      <dd className={styles.attrValue}>{display}</dd>
    </div>
  );
}

function imageCardFromMini(mini: CardMini): CardImageCard {
  return {
    ...mini,
    domains: [],
    type: '',
    supertype: null,
    energy: null,
    might: null,
  };
}

function PrintingItem({
  printing,
  current,
  lang,
}: {
  printing: CardMini;
  current: boolean;
  lang: Lang;
}) {
  const { label } = useEnumLabel();
  const market = printing.price?.market ?? null;
  const name = `${printing.set_id} · #${printing.card_id}`;
  const ariaLabel = `${name}, ${label('rarity', printing.rarity)}`;
  const content = (
    <>
      <CardImage card={imageCardFromMini(printing)} size="thumb" decorative />
      <span className={styles.printingKey}>{name}</span>
      <RarityDot rarity={printing.rarity} />
      <span className={styles.printingPrice}>
        {market !== null ? formatMoney(market, lang) : '—'}
      </span>
    </>
  );

  if (current) {
    return (
      <li className={styles.printingCurrent} aria-current="page" aria-label={ariaLabel}>
        {content}
      </li>
    );
  }

  return (
    <li>
      <Link
        className={styles.printingLink}
        to={`/cards/${printing.set_id}/${printing.card_id}`}
        aria-label={ariaLabel}
      >
        {content}
      </Link>
    </li>
  );
}

function PricesPanel({ card, lang }: { card: CardDetail; lang: Lang }) {
  const { t } = useTranslation('cards');

  if (!card.price) {
    return (
      <section aria-labelledby="prices-title" className={styles.panel}>
        <h2 id="prices-title" className={styles.sectionTitle}>
          {t('detail.prices.title')}
        </h2>
        <p className={styles.muted}>{t('detail.prices.none')}</p>
      </section>
    );
  }

  const market = card.price.market;
  const sourceKey = card.price.market_source ?? '';
  const source = sourceKey ? (t as (k: string) => string)(`detail.prices.source.${sourceKey}`) : '';
  const low = card.price_detail?.columns.low ?? null;
  const avg30 = card.price_detail?.columns.avg30 ?? null;
  const marketFoil = card.price.market_foil;

  return (
    <section aria-labelledby="prices-title" className={styles.panel}>
      <h2 id="prices-title" className={styles.sectionTitle}>
        {t('detail.prices.title')}
      </h2>
      <div className={styles.priceGrid}>
        <div>
          <p className={styles.priceBig}>{market !== null ? formatMoney(market, lang) : '—'}</p>
          <p className={styles.priceLabel}>{t('detail.prices.market')}</p>
          {source && (
            <p className={styles.sourceLine}>{t('detail.prices.sourceLine', { source })}</p>
          )}
        </div>
        <div>
          <p className={styles.priceValue}>{low !== null ? formatMoney(low, lang) : '—'}</p>
          <p className={styles.priceLabel}>{t('detail.prices.low')}</p>
        </div>
        <div>
          <p className={styles.priceValue}>{avg30 !== null ? formatMoney(avg30, lang) : '—'}</p>
          <p className={styles.priceLabel}>{t('detail.prices.avg30')}</p>
        </div>
        {card.foilable && marketFoil !== null && (
          <div>
            <p className={styles.priceValue}>{formatMoney(marketFoil, lang)}</p>
            <p className={styles.priceLabel}>{t('detail.prices.marketFoil')}</p>
          </div>
        )}
      </div>
      <div className={styles.trendRow}>
        <PriceTag price={card.price} trend="7d" size="sm" />
        <PriceTag price={card.price} trend="30d" size="sm" />
      </div>
      {card.price.as_of && (
        <p className={styles.asOf}>
          {t('detail.prices.asOf', { date: formatDate(card.price.as_of, lang) })}
        </p>
      )}
    </section>
  );
}
