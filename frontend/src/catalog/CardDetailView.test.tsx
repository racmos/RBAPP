import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createI18n } from '@/i18n';
import { cardDetail } from '@/test/fixtures/cards';
import { CardDetailView } from './CardDetailView';

async function renderView(props: React.ComponentProps<typeof CardDetailView>) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <CardDetailView {...props} />
        </I18nextProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe('CardDetailView (F2-f S7)', () => {
  it('renders every section with the fixture', async () => {
    await renderView({ presentation: 'page', card: cardDetail });

    // Header
    expect(screen.getByRole('heading', { level: 1, name: cardDetail.name })).toBeVisible();
    expect(screen.getByText('Origins · #79')).toBeVisible();

    // Bans
    expect(screen.getByText(/1v1: banned since/)).toBeVisible();
    expect(screen.getByText(/Dominates the aggro metagame/)).toBeVisible();

    // Prices
    expect(screen.getByText('Prices')).toBeVisible();
    expect(screen.getByText('Market')).toBeVisible();
    expect(screen.getByText('Low')).toBeVisible();
    expect(screen.getByText('30-day avg.')).toBeVisible();
    expect(screen.getByText('Foil market')).toBeVisible();

    // Text
    expect(screen.getByText('Text')).toBeVisible();
    expect(screen.getByText(/Assault 2/)).toBeVisible();

    // Attributes
    expect(screen.getByText('Attributes')).toBeVisible();
    expect(screen.getByText('Energy')).toBeVisible();
    expect(screen.getByText('3')).toBeVisible();

    // My copies
    expect(screen.getByText('My copies')).toBeVisible();
    expect(screen.getByText(/You have 3 copies/)).toBeVisible();
    expect(screen.getByText('Foil')).toBeVisible();
    expect(screen.getByText(/For sale at/)).toBeVisible();

    // Printings
    expect(screen.getByText('Other printings')).toBeVisible();
    expect(screen.getByRole('link', { name: 'OGS · #12, Rare' })).toHaveAttribute(
      'href',
      '/cards/OGS/12',
    );
    expect(screen.getByRole('listitem', { current: 'page' })).toHaveAttribute(
      'aria-label',
      'OGN · #79, Rare',
    );

    // Related
    expect(screen.getByText('Related cards')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Fury Adept' })).toBeVisible();

    // Decks
    expect(screen.getByText('In my decks')).toBeVisible();
    expect(screen.getByRole('link', { name: /Fury Chaos/ })).toHaveAttribute(
      'href',
      '/riftbound/deck/view/3',
    );
  });

  it('links to the collection screen filtered by this card (F3-g S2)', async () => {
    await renderView({ presentation: 'page', card: cardDetail });
    expect(screen.getByRole('link', { name: 'Manage in the collection' })).toHaveAttribute(
      'href',
      expect.stringMatching(/\/collection\?q=OGN-79$/),
    );
  });

  it('shows the empty price state when price is null', async () => {
    await renderView({
      presentation: 'page',
      card: { ...cardDetail, price: null, price_detail: null },
    });
    expect(screen.getByText('This card has no Cardmarket price yet.')).toBeVisible();
    expect(screen.queryByText('Market')).not.toBeInTheDocument();
  });

  it('hides foil market when the card is not foilable', async () => {
    await renderView({ presentation: 'page', card: { ...cardDetail, foilable: false } });
    expect(screen.queryByText('Foil market')).not.toBeInTheDocument();
  });

  it('shows the legal state when there are no bans', async () => {
    await renderView({ presentation: 'page', card: { ...cardDetail, ban_info: [] } });
    expect(screen.getByText('Legal in 1v1 and 2v2')).toBeVisible();
  });

  it('shows the none states for empty collections, related and decks', async () => {
    await renderView({
      presentation: 'page',
      card: { ...cardDetail, my_lines: [], related: [], in_decks: [] },
    });
    expect(screen.getByText("You don't have this card yet.")).toBeVisible();
    expect(screen.getByText('No related cards.')).toBeVisible();
    expect(screen.getByText('Not in any of your decks.')).toBeVisible();
  });

  it('renders modal heading as h2 inside the wrapper', async () => {
    await renderView({ presentation: 'modal', card: cardDetail });
    expect(screen.getByRole('heading', { level: 2, name: cardDetail.name })).toBeVisible();
  });
});
