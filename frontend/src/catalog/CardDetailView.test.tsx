import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router';
import { createI18n } from '@/i18n';
import { cardDetail } from '@/test/fixtures/cards';
import { CardDetailView } from './CardDetailView';

async function renderView(props: React.ComponentProps<typeof CardDetailView>) {
  const i18n = await createI18n('es');
  const { I18nextProvider } = await import('react-i18next');
  return render(
    <MemoryRouter>
      <I18nextProvider i18n={i18n}>
        <CardDetailView {...props} />
      </I18nextProvider>
    </MemoryRouter>,
  );
}

describe('CardDetailView (F2-f S7)', () => {
  it('renders every section with the fixture', async () => {
    await renderView({ presentation: 'page', card: cardDetail });

    // Header
    expect(screen.getByRole('heading', { level: 1, name: cardDetail.name })).toBeVisible();
    expect(screen.getByText('Origen · #79')).toBeVisible();

    // Bans
    expect(screen.getByText(/1v1: baneada desde el/)).toBeVisible();
    expect(screen.getByText(/Dominates the aggro metagame/)).toBeVisible();

    // Prices
    expect(screen.getByText('Precios')).toBeVisible();
    expect(screen.getByText('Mercado')).toBeVisible();
    expect(screen.getByText('Mín.')).toBeVisible();
    expect(screen.getByText('Media 30 d')).toBeVisible();
    expect(screen.getByText('Mercado foil')).toBeVisible();

    // Text
    expect(screen.getByText('Texto')).toBeVisible();
    expect(screen.getByText(/Assault 2/)).toBeVisible();

    // Attributes
    expect(screen.getByText('Atributos')).toBeVisible();
    expect(screen.getByText('Energía')).toBeVisible();
    expect(screen.getByText('3')).toBeVisible();

    // My copies
    expect(screen.getByText('Mis copias')).toBeVisible();
    expect(screen.getByText(/Tienes 3 copias/)).toBeVisible();
    expect(screen.getByText('Foil')).toBeVisible();
    expect(screen.getByText(/En venta a/)).toBeVisible();

    // Printings
    expect(screen.getByText('Otras versiones')).toBeVisible();
    expect(screen.getByRole('link', { name: 'OGS · #12, Rara' })).toHaveAttribute(
      'href',
      '/cards/OGS/12',
    );
    expect(screen.getByRole('listitem', { current: 'page' })).toHaveAttribute(
      'aria-label',
      'OGN · #79, Rara',
    );

    // Related
    expect(screen.getByText('Relacionadas')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Fury Adept' })).toBeVisible();

    // Decks
    expect(screen.getByText('En mis mazos')).toBeVisible();
    expect(screen.getByRole('link', { name: /Fury Chaos/ })).toHaveAttribute(
      'href',
      '/riftbound/deck/view/3',
    );
  });

  it('shows the manage collection link', async () => {
    await renderView({ presentation: 'page', card: cardDetail });
    expect(screen.getByRole('link', { name: 'Gestionar en la colección' })).toHaveAttribute(
      'href',
      '/riftbound/collection',
    );
  });

  it('shows the empty price state when price is null', async () => {
    await renderView({
      presentation: 'page',
      card: { ...cardDetail, price: null, price_detail: null },
    });
    expect(screen.getByText('Esta carta aún no tiene precio en Cardmarket.')).toBeVisible();
    expect(screen.queryByText('Mercado')).not.toBeInTheDocument();
  });

  it('hides foil market when the card is not foilable', async () => {
    await renderView({ presentation: 'page', card: { ...cardDetail, foilable: false } });
    expect(screen.queryByText('Mercado foil')).not.toBeInTheDocument();
  });

  it('shows the legal state when there are no bans', async () => {
    await renderView({ presentation: 'page', card: { ...cardDetail, ban_info: [] } });
    expect(screen.getByText('Legal en 1v1 y 2v2')).toBeVisible();
  });

  it('shows the none states for empty collections, related and decks', async () => {
    await renderView({
      presentation: 'page',
      card: { ...cardDetail, my_lines: [], related: [], in_decks: [] },
    });
    expect(screen.getByText('Todavía no tienes esta carta.')).toBeVisible();
    expect(screen.getByText('No hay cartas relacionadas.')).toBeVisible();
    expect(screen.getByText('No está en ningún mazo tuyo.')).toBeVisible();
  });

  it('renders modal heading as h2 inside the wrapper', async () => {
    await renderView({ presentation: 'modal', card: cardDetail });
    expect(screen.getByRole('heading', { level: 2, name: cardDetail.name })).toBeVisible();
  });
});
