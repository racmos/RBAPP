import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { PricePoint } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { down } from '@/lib/breakpoints';
import { formatDate, formatMoney, localeFor, type Lang } from '@/lib/format';
import { linearScale, niceTicks } from '@/lib/scale';
import { useMediaQuery } from '@/lib/useMediaQuery';
import styles from './PriceChart.module.css';

type SeriesKey = 'market' | 'market_foil';

type PriceChartProps = {
  points: PricePoint[];
  series: SeriesKey[];
  lang: Lang;
  height?: number;
  title: string;
};

const MARGIN = { top: 16, right: 16, bottom: 36, left: 52 };
const FALLBACK_WIDTH = 600;

function safeId(raw: string): string {
  return raw.replace(/[^a-zA-Z0-9-]/g, '-');
}

function axisDateFormat(date: Date, lang: Lang, rangeMs: number): string {
  const locale = localeFor(lang);
  const days = rangeMs / (1000 * 60 * 60 * 24);
  if (days <= 90) {
    return new Intl.DateTimeFormat(locale, {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    }).format(date);
  }
  return new Intl.DateTimeFormat(locale, {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

function xTickIndices(count: number): number[] {
  if (count <= 6) return Array.from({ length: count }, (_, i) => i);
  const step = Math.ceil((count - 1) / 5);
  const indices: number[] = [0];
  for (let i = step; i < count - 1; i += step) indices.push(i);
  indices.push(count - 1);
  return indices;
}

export function PriceChart({ points, series, lang, height, title }: PriceChartProps) {
  const { t } = useTranslation('cards');
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(FALLBACK_WIDTH);
  const isMobile = useMediaQuery(down('md'));
  const chartHeight = height ?? (isMobile ? 200 : 260);
  const gradientId = safeId(useId());
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const dates = useMemo(() => points.map((p) => new Date(p.date).getTime()), [points]);
  const rangeMs = dates[dates.length - 1] - dates[0];

  const visibleValues = useMemo(() => {
    const values: number[] = [];
    for (const point of points) {
      for (const key of series) {
        const value = point[key];
        if (value !== null) values.push(value);
      }
    }
    return values;
  }, [points, series]);

  const yMin = visibleValues.length ? Math.min(...visibleValues) : 0;
  const yMax = visibleValues.length ? Math.max(...visibleValues) : 0;
  const yTicks = useMemo(() => niceTicks(yMin, yMax, 5), [yMin, yMax]);

  const plotWidth = Math.max(0, width - MARGIN.left - MARGIN.right);
  const plotHeight = Math.max(0, chartHeight - MARGIN.top - MARGIN.bottom);

  const xScale = useMemo(() => {
    if (points.length <= 1) return () => plotWidth / 2;
    return linearScale([dates[0], dates[dates.length - 1]], [0, plotWidth]);
  }, [dates, plotWidth, points.length]);

  const yScale = useMemo(() => {
    if (yTicks.length === 1) return () => plotHeight / 2;
    return linearScale([yTicks[0], yTicks[yTicks.length - 1]], [plotHeight, 0]);
  }, [yTicks, plotHeight]);

  const summary = useMemo(() => {
    if (points.length === 0) return '';
    const marketValues = points.map((p) => p.market).filter((v): v is number => v !== null);
    const first = marketValues[0] ?? 0;
    const last = marketValues[marketValues.length - 1] ?? 0;
    const min = marketValues.length ? Math.min(...marketValues) : 0;
    const max = marketValues.length ? Math.max(...marketValues) : 0;
    return t('chart.summary', {
      from: formatDate(points[0].date, lang),
      to: formatDate(points[points.length - 1].date, lang),
      first: formatMoney(first, lang),
      last: formatMoney(last, lang),
      min: formatMoney(min, lang),
      max: formatMoney(max, lang),
    });
  }, [points, lang, t]);

  function linePath(key: SeriesKey): string {
    let d = '';
    let pending = true;
    for (let i = 0; i < points.length; i++) {
      const value = points[i][key];
      if (value === null) {
        pending = true;
        continue;
      }
      const x = MARGIN.left + xScale(dates[i]);
      const y = MARGIN.top + yScale(value);
      if (pending) {
        d += `${d ? ' ' : ''}M ${x} ${y}`;
        pending = false;
      } else {
        d += ` L ${x} ${y}`;
      }
    }
    return d;
  }

  function areaPath(): string {
    const path = linePath('market');
    if (!path) return '';
    let firstIndex = -1;
    let lastIndex = -1;
    for (let i = 0; i < points.length; i++) {
      if (points[i].market !== null) {
        if (firstIndex === -1) firstIndex = i;
        lastIndex = i;
      }
    }
    if (firstIndex === -1) return '';
    const xLast = MARGIN.left + xScale(dates[lastIndex]);
    const xFirst = MARGIN.left + xScale(dates[firstIndex]);
    const yBottom = MARGIN.top + plotHeight;
    return `${path} L ${xLast} ${yBottom} L ${xFirst} ${yBottom} Z`;
  }

  const lastBySeries = useMemo(() => {
    return series
      .map((key) => {
        for (let i = points.length - 1; i >= 0; i--) {
          const value = points[i][key];
          if (value !== null) {
            return { key, index: i, value } as { key: SeriesKey; index: number; value: number };
          }
        }
        return null;
      })
      .filter((item): item is { key: SeriesKey; index: number; value: number } => item !== null);
  }, [points, series]);

  const activePoint = activeIndex !== null ? points[activeIndex] : null;
  const liveText =
    activePoint !== null
      ? t('chart.point', {
          date: formatDate(activePoint.date, lang),
          values: series
            .map((key) => {
              const value = activePoint[key];
              return `${t(`chart.series.${key}`)}: ${value !== null ? formatMoney(value, lang) : '—'}`;
            })
            .join(', '),
        })
      : '';

  function handlePointerMove(event: React.PointerEvent<SVGRectElement>) {
    if (points.length <= 1) return;
    const svg = event.currentTarget.ownerSVGElement;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const x = event.clientX - rect.left - MARGIN.left;
    const ratio = Math.max(0, Math.min(1, x / plotWidth));
    const index = Math.round(ratio * (points.length - 1));
    setActiveIndex(index);
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (points.length === 0) return;
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      setActiveIndex((index) => (index === null ? points.length - 1 : Math.max(0, index - 1)));
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      setActiveIndex((index) => (index === null ? 0 : Math.min(points.length - 1, index + 1)));
    } else if (event.key === 'Home') {
      event.preventDefault();
      setActiveIndex(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      setActiveIndex(points.length - 1);
    } else if (event.key === 'Escape') {
      setActiveIndex(null);
    }
  }

  const xIndices = xTickIndices(points.length);
  const crosshairX = activeIndex !== null ? MARGIN.left + xScale(dates[activeIndex]) : null;

  if (points.length === 0) {
    return <div className={styles.empty}>{t('chart.empty')}</div>;
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <span className={styles.title}>{title}</span>
        <span className={styles.legend}>
          {series.map((key) => (
            <span key={key} className={styles.legendItem}>
              <span className={key === 'market' ? styles.marketLine : styles.foilLine} />
              {t(`chart.series.${key}`)}
            </span>
          ))}
        </span>
      </div>

      <div ref={containerRef} className={styles.chart}>
        <svg
          role="group"
          aria-label={summary}
          tabIndex={0}
          width={width}
          height={chartHeight}
          className={styles.plot}
          onKeyDown={handleKeyDown}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Grid and Y ticks */}
          {yTicks.map((tick, index) => {
            const y = MARGIN.top + yScale(tick);
            return (
              <g key={index}>
                <line
                  x1={MARGIN.left}
                  y1={y}
                  x2={MARGIN.left + plotWidth}
                  y2={y}
                  className={styles.gridLine}
                  vectorEffect="non-scaling-stroke"
                />
                <text x={MARGIN.left - 8} y={y + 4} textAnchor="end" className={styles.axisText}>
                  {formatMoney(tick, lang)}
                </text>
              </g>
            );
          })}

          {/* X ticks */}
          {xIndices.map((index) => {
            const x = MARGIN.left + xScale(dates[index]);
            return (
              <text
                key={index}
                x={x}
                y={chartHeight - 10}
                textAnchor="middle"
                className={styles.axisText}
              >
                {axisDateFormat(new Date(dates[index]), lang, rangeMs)}
              </text>
            );
          })}

          {/* Area under market series */}
          {series.includes('market') && points.length > 1 && (
            <path
              d={areaPath()}
              className={styles.marketArea}
              style={{ fill: `url(#${gradientId})` }}
            />
          )}

          {/* Series lines */}
          {series.includes('market') && points.length > 1 && (
            <path
              d={linePath('market')}
              className={styles.marketSeries}
              vectorEffect="non-scaling-stroke"
            />
          )}
          {series.includes('market_foil') && points.length > 1 && (
            <path
              d={linePath('market_foil')}
              className={styles.foilSeries}
              strokeDasharray="6 4"
              vectorEffect="non-scaling-stroke"
            />
          )}

          {/* Last point markers */}
          {lastBySeries.map(({ key, index, value }) => {
            const x = MARGIN.left + xScale(dates[index]);
            const y = MARGIN.top + yScale(value);
            return (
              <circle
                key={key}
                cx={x}
                cy={y}
                r={4}
                className={styles.marker}
                fill={key === 'market' ? 'var(--accent)' : 'var(--gold)'}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}

          {/* Single point: marker + value label */}
          {points.length === 1 && points[0].market !== null && (
            <g>
              <circle
                cx={MARGIN.left + plotWidth / 2}
                cy={MARGIN.top + yScale(points[0].market)}
                r={4}
                className={styles.marker}
                fill="var(--accent)"
              />
              <text
                x={MARGIN.left + plotWidth / 2 + 12}
                y={MARGIN.top + yScale(points[0].market) + 4}
                className={styles.axisText}
              >
                {formatMoney(points[0].market, lang)}
              </text>
            </g>
          )}

          {/* Interaction surface */}
          {points.length > 1 && (
            <>
              <rect
                x={MARGIN.left}
                y={MARGIN.top}
                width={plotWidth}
                height={plotHeight}
                fill="transparent"
                onPointerMove={handlePointerMove}
                onPointerLeave={() => setActiveIndex(null)}
              />
              {crosshairX !== null && (
                <line
                  x1={crosshairX}
                  y1={MARGIN.top}
                  x2={crosshairX}
                  y2={MARGIN.top + plotHeight}
                  className={styles.crosshair}
                  vectorEffect="non-scaling-stroke"
                />
              )}
            </>
          )}
        </svg>

        {activePoint !== null && crosshairX !== null && (
          <div
            className={styles.tooltip}
            style={{
              left: crosshairX,
              top: MARGIN.top + plotHeight / 2,
            }}
          >
            <p className={styles.tooltipDate}>{formatDate(activePoint.date, lang)}</p>
            <div className={styles.tooltipRow}>
              {series.map((key) => (
                <span key={key}>
                  {t(`chart.series.${key}`)}:{' '}
                  {activePoint[key] !== null ? formatMoney(activePoint[key] as number, lang) : '—'}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div aria-live="polite" className={styles.srOnly} role="status">
        {liveText}
      </div>

      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowTable((s) => !s)}
        aria-expanded={showTable}
      >
        {showTable ? t('chart.hideTable') : t('chart.showTable')}
      </Button>

      {showTable && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption>{t('chart.table.caption', { name: title })}</caption>
            <thead>
              <tr>
                <th scope="col">{t('chart.table.date')}</th>
                <th scope="col">{t('chart.table.market')}</th>
                {series.includes('market_foil') && (
                  <th scope="col">{t('chart.table.market_foil')}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {[...points].reverse().map((point, index) => (
                <tr key={index}>
                  <td>{formatDate(point.date, lang)}</td>
                  <td className={styles.numeric}>
                    {point.market !== null ? formatMoney(point.market, lang) : '—'}
                  </td>
                  {series.includes('market_foil') && (
                    <td className={styles.numeric}>
                      {point.market_foil !== null ? formatMoney(point.market_foil, lang) : '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
