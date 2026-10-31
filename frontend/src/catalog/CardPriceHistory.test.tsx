import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { I18nextProvider } from 'react-i18next';
import { API, failure, priceHistory, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { createI18n } from '@/i18n';
import { setViewport } from '@/test/viewport';
import { cardDetail } from '@/test/fixtures/cards';
import type { PricePoint } from '@/api/types';
import { CardPriceHistory } from './CardPriceHistory';

const pricePoints: PricePoint[] = [
  { date: '2026-10-18', market: 1.15, low: 1.05, avg7: 1.12, avg30: 1.14, market_foil: 2.35 },
  { date: '2026-10-19', market: 1.18, low: 1.08, avg7: 1.14, avg30: 1.15, market_foil: 2.4 },
  { date: '2026-10-20', market: 1.21, low: 1.1, avg7: 1.17, avg30: 1.16, market_foil: 2.45 },
];

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

function freshClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

async function renderHistory(props: React.ComponentProps<typeof CardPriceHistory>, width = 1280) {
  signedInApi();
  setViewport(width);
  const i18n = await createI18n();
  const queryClient = freshClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <CardPriceHistory {...props} />
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

const defaultProps = {
  setId: cardDetail.set_id,
  cardId: cardDetail.card_id,
  foilable: cardDetail.foilable,
  name: cardDetail.name,
};

describe('CardPriceHistory (F2-g S6)', () => {
  it('shows the price history section with 90d selected by default', async () => {
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory([])));
    await renderHistory(defaultProps);
    expect(await screen.findByRole('heading', { name: 'Price history' }, LONG)).toBeVisible();
    expect(screen.getByRole('radio', { name: '90 d' })).toBeChecked();
  });

  it('changes range and stores the choice', async () => {
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory(pricePoints)));
    await renderHistory(defaultProps);
    await screen.findByRole('button', { name: 'Show as table' }, LONG);
    await userEvent.click(screen.getByRole('radio', { name: '30 d' }));
    await waitFor(() => expect(screen.getByRole('radio', { name: '30 d' })).toBeChecked());
    expect(localStorage.getItem('rb_price_range')).toBe('30d');
  });

  it('remembers the last selected range', async () => {
    localStorage.setItem('rb_price_range', '1y');
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory([])));
    await renderHistory(defaultProps);
    await screen.findByRole('heading', { name: 'Price history' }, LONG);
    expect(screen.getByRole('radio', { name: '1 year' })).toBeChecked();
  });

  it('falls back to 90d when the stored range is invalid', async () => {
    localStorage.setItem('rb_price_range', 'bad');
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory([])));
    await renderHistory(defaultProps);
    await screen.findByRole('heading', { name: 'Price history' }, LONG);
    expect(screen.getByRole('radio', { name: '90 d' })).toBeChecked();
  });

  it('shows the foil series when the card is foilable', async () => {
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory(pricePoints)));
    await renderHistory(defaultProps);
    await screen.findByRole('heading', { name: 'Price history' }, LONG);
    expect(await screen.findByText('Foil market', {}, LONG)).toBeVisible();
  });

  it('hides the foil series when the card is not foilable', async () => {
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory(pricePoints)));
    await renderHistory({ ...defaultProps, foilable: false });
    await screen.findByRole('heading', { name: 'Price history' }, LONG);
    await screen.findByText('Market', {}, LONG);
    expect(screen.queryByText('Foil market')).not.toBeInTheDocument();
  });

  it('shows a loading skeleton and then the chart', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, async () => {
        await gate;
        return priceHistory([]);
      }),
    );
    await renderHistory(defaultProps);
    expect(await screen.findByText('Loading history', {}, LONG)).toBeInTheDocument();
    release();
    expect(await screen.findByText('No price history yet.', {}, LONG)).toBeVisible();
  });

  it('shows an error state with retry', async () => {
    let failing = true;
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, () =>
        failing ? failure(500, { message: 'boom' }) : priceHistory([]),
      ),
    );
    await renderHistory(defaultProps);
    const alert = await screen.findByRole('alert', {}, LONG);
    expect(alert).toBeVisible();
    failing = false;
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('No price history yet.', {}, LONG)).toBeVisible();
  });
});

describe('CardPriceHistory axe (F2-g AC5)', () => {
  it('has no violations at 390 px', async () => {
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory(pricePoints)));
    await renderHistory(defaultProps, 390);
    await screen.findByRole('heading', { name: 'Price history' }, LONG);
    const toggle = await screen.findByRole('button', { name: 'Show as table' }, LONG);
    await userEvent.click(toggle);
    expect(await screen.findByRole('table', {}, LONG)).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations at 1280 px', async () => {
    server.use(http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory(pricePoints)));
    await renderHistory(defaultProps, 1280);
    await screen.findByRole('heading', { name: 'Price history' }, LONG);
    const toggle = await screen.findByRole('button', { name: 'Show as table' }, LONG);
    await userEvent.click(toggle);
    expect(await screen.findByRole('table', {}, LONG)).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
