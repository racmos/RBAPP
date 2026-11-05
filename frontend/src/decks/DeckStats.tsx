import { useId, useMemo, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import type { DeckContentV2 } from '@/api/types';
import { DomainPips } from '@/components/card';
import { useEnumLabel } from '@/i18n';
import { domainColor } from '@/lib/domains';
import { formatNumber } from '@/lib/format';
import { STAT_GROUPS, deckStats, type DeckStats as Stats, type DomainRow } from './deckStats';
import type { CardBook } from './editor';
import styles from './DeckStats.module.css';

/** One decimal, "—" plus a spoken "No value" when the deck has none. */
function Average({ value }: { value: number | null }) {
  const { t } = useTranslation('decks');
  if (value === null) {
    return (
      <>
        <span aria-hidden="true">—</span>
        <span className="sr-only">{t('stats.noValue')}</span>
      </>
    );
  }
  return <>{formatNumber(Math.round(value * 10) / 10)}</>;
}

function Tiles({ stats }: { stats: Stats }) {
  const { t } = useTranslation('decks');
  const tiles = [
    ['mainCount', formatNumber(stats.mainCount)],
    ['avgEnergy', <Average key="energy" value={stats.avgEnergy} />],
    ['avgMight', <Average key="might" value={stats.avgMight} />],
    ['powerCards', formatNumber(stats.powerCards)],
  ] as const;
  return (
    <dl className={styles.tiles}>
      {tiles.map(([key, value]) => (
        <div key={key} className={styles.tile}>
          <dt>{t(`stats.${key}`)}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A chart: the title names the figure, the bars are drawn for the eye only and every value is
 *  also in `values`, a visually hidden list screen readers read. */
function Chart({
  title,
  valuesLabel,
  values,
  children,
  extra,
}: {
  title: string;
  valuesLabel: string;
  values: string[];
  children: ReactNode;
  extra?: ReactNode;
}) {
  const id = useId();
  return (
    <figure className={styles.figure} aria-labelledby={id}>
      <figcaption>
        <h2 id={id} className={styles.title}>
          {title}
        </h2>
      </figcaption>
      <div className={styles.bars} aria-hidden="true">
        {children}
      </div>
      {extra}
      <ul className="sr-only" aria-label={valuesLabel}>
        {values.map((text, index) => (
          <li key={index}>{text}</li>
        ))}
      </ul>
    </figure>
  );
}

/** One column of a bar chart: the count above, the bar, the value below. */
function Column({
  label,
  total,
  max,
  children,
}: {
  label: string;
  total: number;
  max: number;
  children: ReactNode;
}) {
  return (
    <div className={styles.column}>
      <span className={styles.count}>{total > 0 ? total : ''}</span>
      <span className={styles.track}>
        <span className={styles.stack} style={{ height: `${max > 0 ? (total / max) * 100 : 0}%` }}>
          {children}
        </span>
      </span>
      <span className={styles.axis}>{label}</span>
    </div>
  );
}

function EnergyCurve({ stats }: { stats: Stats }) {
  const { t } = useTranslation('decks');
  const max = Math.max(...stats.energyCurve.map((bucket) => bucket.total));
  const labelOf = (value: number, top: boolean) =>
    top ? t('stats.top', { value }) : String(value);
  const values = stats.energyCurve.map((bucket) => {
    const text = t('stats.energyBucket', {
      value: labelOf(bucket.value, bucket.top),
      count: bucket.total,
    });
    const groups = STAT_GROUPS.filter((group) => bucket.groups[group] > 0).map((group) =>
      t('stats.groupCount', { group: t(`stats.group.${group}`), count: bucket.groups[group] }),
    );
    return groups.length > 0 ? t('stats.withGroups', { text, groups: groups.join(', ') }) : text;
  });
  const legend = (
    <ul className={styles.legend} aria-label={t('stats.groupsLabel')}>
      {STAT_GROUPS.map((group) => (
        <li key={group}>
          <span className={styles.swatch} data-group={group} aria-hidden="true" />{' '}
          {t(`stats.group.${group}`)}
        </li>
      ))}
    </ul>
  );
  return (
    <Chart
      title={t('stats.energyCurve')}
      valuesLabel={t('stats.energyValues')}
      values={values}
      extra={legend}
    >
      {stats.energyCurve.map((bucket) => (
        <Column
          key={bucket.value}
          label={labelOf(bucket.value, bucket.top)}
          total={bucket.total}
          max={max}
        >
          {STAT_GROUPS.map((group) =>
            bucket.groups[group] > 0 ? (
              <span
                key={group}
                className={styles.segment}
                data-group={group}
                style={{ flexGrow: bucket.groups[group] }}
              />
            ) : null,
          )}
        </Column>
      ))}
    </Chart>
  );
}

function UnitMight({ stats }: { stats: Stats }) {
  const { t } = useTranslation('decks');
  const max = Math.max(...stats.mightHistogram.map((bucket) => bucket.count));
  const labelOf = (value: number, top: boolean) =>
    top ? t('stats.top', { value }) : String(value);
  return (
    <Chart
      title={t('stats.might')}
      valuesLabel={t('stats.mightValues')}
      values={stats.mightHistogram.map((bucket) =>
        t('stats.mightBucket', { value: labelOf(bucket.value, bucket.top), count: bucket.count }),
      )}
    >
      {stats.mightHistogram.map((bucket) => (
        <Column
          key={bucket.value}
          label={labelOf(bucket.value, bucket.top)}
          total={bucket.count}
          max={max}
        >
          {bucket.count > 0 && <span className={styles.segment} data-group="unit" />}
        </Column>
      ))}
    </Chart>
  );
}

const percent = (share: number) => Math.round(share * 100);

/** One domain: its pip and name, then cards, power and runes with a share bar each. */
function DomainBlock({ row }: { row: DomainRow }) {
  const { t } = useTranslation('decks');
  const { label } = useEnumLabel();
  const id = useId();
  const lines = [
    ['domainCards', row.cards, row.cardShare],
    ['domainPower', row.power, row.powerShare],
    ['domainRunes', row.runes, row.runeShare],
  ] as const;
  return (
    <div role="group" aria-labelledby={id} className={styles.domain}>
      <span className={styles.domainName}>
        <DomainPips domains={[row.domain]} size={16} />
        <span id={id}>{label('domain', row.domain)}</span>
      </span>
      <ul className={styles.shares}>
        {lines.map(([key, count, share]) => (
          <li key={key}>
            <span className={styles.shareText}>
              {t(`stats.${key}`, { count, share: percent(share) })}
            </span>
            <span className={styles.shareTrack} aria-hidden="true">
              <span
                className={styles.shareFill}
                style={{ width: `${percent(share)}%`, background: domainColor(row.domain) }}
              />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PowerByDomain({ stats }: { stats: Stats }) {
  const { t } = useTranslation('decks');
  const id = useId();
  return (
    <figure className={styles.figure} aria-labelledby={id}>
      <figcaption>
        <h2 id={id} className={styles.title}>
          {t('stats.domains')}
        </h2>
      </figcaption>
      <div className={styles.domains}>
        {stats.powerByDomain.map((row) => (
          <DomainBlock key={row.domain} row={row} />
        ))}
      </div>
      <p className={styles.hint}>{t('stats.domainsHint')}</p>
    </figure>
  );
}

function Keywords({ stats }: { stats: Stats }) {
  const { t } = useTranslation('decks');
  const id = useId();
  return (
    <section className={styles.figure} aria-labelledby={id}>
      <h2 id={id} className={styles.title}>
        {t('stats.keywords')}
      </h2>
      {stats.keywords.length === 0 ? (
        <p className={styles.hint}>{t('stats.noKeywords')}</p>
      ) : (
        <ul className={styles.keywords}>
          {stats.keywords.map((keyword) => (
            <li key={keyword.name}>
              <span>{keyword.name}</span>
              <span className={styles.keywordCount}>{formatNumber(keyword.count)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className={styles.hint}>{t('stats.keywordsHint')}</p>
    </section>
  );
}

/**
 * The workspace Stats tab (F5-i step 4, owner image 5): summary tiles, energy curve by group,
 * power and runes by domain, unit might and keywords, all from `deckStats` over the main deck,
 * so they follow every edit. Each chart draws its bars for the eye and lists its values as text.
 */
export function DeckStats({ content, book }: { content: DeckContentV2; book: CardBook }) {
  const { t } = useTranslation('decks');
  const stats = useMemo(() => deckStats(content, book), [content, book]);
  if (stats.mainCount === 0) return <p className={styles.empty}>{t('stats.empty')}</p>;
  return (
    <div className={styles.stats}>
      <Tiles stats={stats} />
      <EnergyCurve stats={stats} />
      <PowerByDomain stats={stats} />
      <UnitMight stats={stats} />
      <Keywords stats={stats} />
    </div>
  );
}
