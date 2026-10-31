import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import type { PricePoint } from '@/api/types';
import { createI18n } from '@/i18n';
import { I18nextProvider } from 'react-i18next';
import { PriceChart } from './PriceChart';
import styles from './PriceChart.module.css';

const points: PricePoint[] = [
  { date: '2026-07-22', market: 1.04, low: 0.98, avg7: 1.0, avg30: 1.01, market_foil: 2.1 },
  { date: '2026-08-01', market: 1.08, low: 1.02, avg7: 1.05, avg30: 1.04, market_foil: 2.2 },
  { date: '2026-08-15', market: 1.12, low: 1.06, avg7: 1.09, avg30: 1.08, market_foil: 2.3 },
  { date: '2026-09-01', market: null, low: null, avg7: null, avg30: null, market_foil: null },
  { date: '2026-09-15', market: 1.18, low: 1.1, avg7: 1.14, avg30: 1.15, market_foil: 2.4 },
  { date: '2026-10-20', market: 1.21, low: 1.15, avg7: 1.19, avg30: 1.2, market_foil: 2.5 },
];

async function renderChart(props: React.ComponentProps<typeof PriceChart>) {
  const i18n = await createI18n();
  return render(
    <I18nextProvider i18n={i18n}>
      <PriceChart {...props} />
    </I18nextProvider>,
  );
}

describe('PriceChart (F2-g S3-S5)', () => {
  it('renders Y ticks and grid lines', async () => {
    await renderChart({ points, series: ['market'], title: 'Price' });
    const yLabels = screen.getAllByText(/€/);
    expect(yLabels.length).toBeGreaterThanOrEqual(2);
    expect(document.querySelectorAll(`.${styles.gridLine}`).length).toBeGreaterThanOrEqual(2);
  });

  it('gives two charts different gradient ids', async () => {
    const i18n = await createI18n();
    const { container } = render(
      <I18nextProvider i18n={i18n}>
        <PriceChart points={points} series={['market']} title="A" />
        <PriceChart points={points} series={['market']} title="B" />
      </I18nextProvider>,
    );
    const fills = Array.from(container.querySelectorAll('linearGradient'));
    const ids = fills.map((el) => el.id);
    expect(new Set(ids).size).toBe(2);
  });

  it('breaks the line at null values', async () => {
    await renderChart({ points, series: ['market'], title: 'Price' });
    const path = document.querySelector(`.${styles.marketSeries}`);
    expect(path?.getAttribute('d')).toMatch(/M.*M/);
  });

  it('renders a marker and value for a single point', async () => {
    await renderChart({ points: [points[0]], series: ['market'], title: 'Price' });
    expect(document.querySelectorAll('circle').length).toBeGreaterThanOrEqual(1);
    expect(document.querySelectorAll(`.${styles.marketSeries}`).length).toBe(0);
  });

  it('renders an empty state for zero points', async () => {
    await renderChart({ points: [], series: ['market'], title: 'Price' });
    expect(screen.getByText('No price history yet.')).toBeVisible();
  });

  it('renders the foil series with a dashed stroke', async () => {
    await renderChart({ points, series: ['market', 'market_foil'], title: 'Price' });
    const foil = document.querySelector(`.${styles.foilSeries}`);
    expect(foil).toBeInTheDocument();
    expect(foil?.getAttribute('stroke-dasharray')).toBeTruthy();
  });

  it('toggles the table and shows a caption', async () => {
    await renderChart({ points, series: ['market'], title: 'Ayla' });
    const button = screen.getByRole('button', { name: 'Show as table' });
    await userEvent.click(button);
    expect(screen.getByRole('table')).toBeVisible();
    expect(screen.getByText('Daily prices of Ayla')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Hide table' })).toBeVisible();
  });

  it('writes the active point to the live region on keyboard navigation', async () => {
    await renderChart({ points, series: ['market'], title: 'Price' });
    const plot = screen.getByRole('group');
    plot.focus();
    await userEvent.keyboard('{Home}');
    await userEvent.keyboard('{ArrowRight}');
    const live = screen.getByRole('status');
    expect(live).toHaveTextContent('1 Aug 2026');
    await userEvent.keyboard('{End}');
    expect(live).toHaveTextContent('20 Oct 2026');
    await userEvent.keyboard('{Escape}');
    expect(live).toHaveTextContent('');
  });

  it('has an English summary accessible name with English dates and amounts', async () => {
    await renderChart({ points, series: ['market'], title: 'Price' });
    const plot = screen.getByRole('group');
    expect(plot).toHaveAccessibleName(
      'Market price from 22 Jul 2026 to 20 Oct 2026: 1.04 € to 1.21 € (low 1.04 €, high 1.21 €).',
    );
  });
});
