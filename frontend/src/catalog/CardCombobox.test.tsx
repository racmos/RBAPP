import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { I18nextProvider } from 'react-i18next';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { CardSummary } from '@/api/types';
import { createI18n, type Lang } from '@/i18n';
import { cardList, champion, foilCommon, noPrice } from '@/test/fixtures/cards';
import { API } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { CardCombobox, type CardComboboxProps } from './CardCombobox';

const LONG = { timeout: 5000 };

async function renderCombobox(props: Partial<CardComboboxProps> = {}, lang: Lang = 'es') {
  const i18n = await createI18n(lang);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onSelect = vi.fn<(card: CardSummary) => void>();
  const user = userEvent.setup();
  const result = render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <CardCombobox label="Carta" onSelect={onSelect} {...props} />
      </QueryClientProvider>
    </I18nextProvider>,
  );
  return { ...result, onSelect, user };
}

/** Records every `GET /cards` the combobox makes and answers with `items`. */
function recordCards(items: CardSummary[] = cardList.items, total = items.length): { urls: URL[] } {
  const seen: { urls: URL[] } = { urls: [] };
  server.use(
    http.get(`${API}/cards`, ({ request }) => {
      seen.urls.push(new URL(request.url));
      return HttpResponse.json({
        success: true,
        data: { items },
        meta: { ...cardList.meta, per_page: 20, total, pages: 1 },
      });
    }),
  );
  return seen;
}

const input = () => screen.getByRole('combobox');
const status = () => screen.getByRole('status');
const popupState = (name: string) => document.querySelector(`[data-state="${name}"]`);

afterEach(() => {
  vi.restoreAllMocks();
});

describe('CardCombobox search (F2-k S1, S2)', () => {
  it('makes no request and keeps the list closed below 2 characters', async () => {
    const seen = recordCards();
    const { user } = await renderCombobox();
    await user.type(input(), ' a ');
    await new Promise((resolve) => setTimeout(resolve, 450));
    expect(seen.urls).toHaveLength(0);
    expect(input()).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('debounces typing into one request with q, per_page=20 and sort=name', async () => {
    const seen = recordCards();
    const { user } = await renderCombobox();
    await user.type(input(), 'ayl');
    await screen.findByRole('listbox', {}, LONG);
    expect(seen.urls).toHaveLength(1);
    const params = seen.urls[0].searchParams;
    expect(params.get('q')).toBe('ayl');
    expect(params.get('per_page')).toBe('20');
    expect(params.get('sort')).toBe('name');
  });

  it('passes the filters through to the API', async () => {
    const seen = recordCards();
    const { user } = await renderCombobox({
      filters: { base_only: true, exclude_supertype: ['Token'], set: ['OGN'] },
    });
    await user.type(input(), 'ember');
    await screen.findByRole('listbox', {}, LONG);
    const params = seen.urls[0].searchParams;
    expect(params.get('base_only')).toBe('true');
    expect(params.getAll('exclude_supertype')).toEqual(['Token']);
    expect(params.getAll('set')).toEqual(['OGN']);
  });

  it('aborts the previous request when the text changes', async () => {
    server.use(
      http.get(`${API}/cards`, async ({ request }) => {
        await delay(new URL(request.url).searchParams.get('q') === 'em' ? 1500 : 0);
        return HttpResponse.json({
          success: true,
          data: { items: [foilCommon] },
          meta: { ...cardList.meta, per_page: 20, total: 1, pages: 1 },
        });
      }),
    );
    const signals = new Map<string, AbortSignal | null | undefined>();
    const realFetch = globalThis.fetch;
    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input), 'http://x');
      signals.set(url.searchParams.get('q') ?? '', init?.signal);
      return realFetch(input, init);
    });
    const { user } = await renderCombobox();
    await user.type(input(), 'em');
    // the request for "em" is in flight
    await waitFor(() => expect(status()).toHaveTextContent('Buscando…'), LONG);
    await waitFor(() => expect(signals.has('em')).toBe(true), LONG);
    await user.type(input(), 'b');
    await screen.findByRole('option', { name: /Ember Wisp/ }, LONG);
    expect(signals.get('em')?.aborted).toBe(true);
    expect(signals.get('emb')?.aborted).toBe(false);
  });

  it('shows the card in each option: thumb, name, set and number, type, domains and price', async () => {
    recordCards([champion, noPrice]);
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    const options = await screen.findAllByRole('option', {}, LONG);
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("Ayla, Fury's Champion");
    expect(options[0]).toHaveTextContent('OGN · #79');
    expect(options[0]).toHaveTextContent('1,21 €');
    expect(options[0].querySelector('img')).toHaveAttribute('alt', '');
    expect(options[1]).toHaveTextContent('No Price Yet');
    expect(options[1]).toHaveTextContent('—');
  });

  it('adds a non-selectable "more" row when the total is above 20', async () => {
    const twenty = Array.from({ length: 20 }, (_, index) => ({
      ...champion,
      card_id: String(index + 1),
      key: `OGN-${index + 1}`,
    }));
    recordCards(twenty, 35);
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    expect(screen.getAllByRole('option')).toHaveLength(20);
    expect(screen.getByText('y 15 más: afina la búsqueda')).toBeVisible();
  });
});

describe('CardCombobox keyboard and pointer (F2-k S3)', () => {
  it('follows the ARIA 1.2 combobox pattern', async () => {
    recordCards([champion, foilCommon]);
    const { user } = await renderCombobox();
    expect(input()).toHaveAttribute('aria-autocomplete', 'list');
    expect(input()).toHaveAttribute('aria-expanded', 'false');
    await user.type(input(), 'ay');
    const listbox = await screen.findByRole('listbox', {}, LONG);
    const options = screen.getAllByRole('option');
    expect(input()).toHaveAttribute('aria-expanded', 'true');
    expect(input()).toHaveAttribute('aria-controls', listbox.id);
    expect(input()).toHaveAttribute('aria-activedescendant', options[0].id);
    expect(options[0]).toHaveAttribute('aria-selected', 'true');
    expect(options[1]).toHaveAttribute('aria-selected', 'false');
  });

  it('moves with the arrows (wrapping), Home and End, and selects with Enter', async () => {
    recordCards([champion, foilCommon, noPrice]);
    const { user, onSelect } = await renderCombobox();
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    const options = screen.getAllByRole('option');
    const active = () => input().getAttribute('aria-activedescendant');

    await user.keyboard('{ArrowDown}');
    expect(active()).toBe(options[1].id);
    await user.keyboard('{ArrowDown}{ArrowDown}');
    expect(active()).toBe(options[0].id); // wrapped past the end
    await user.keyboard('{ArrowUp}');
    expect(active()).toBe(options[2].id); // wrapped past the start
    await user.keyboard('{Home}');
    expect(active()).toBe(options[0].id);
    await user.keyboard('{End}');
    expect(active()).toBe(options[2].id);

    await user.keyboard('{Enter}');
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(noPrice);
    expect(input()).toHaveValue(''); // clearOnSelect defaults to true
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('tells onEnterSelect, after onSelect, when the card was picked with Enter', async () => {
    recordCards([champion, foilCommon]);
    const onEnterSelect = vi.fn<(card: CardSummary) => void>();
    const { user, onSelect } = await renderCombobox({ onEnterSelect });
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    await user.keyboard('{ArrowDown}{Enter}');
    expect(onSelect).toHaveBeenCalledWith(foilCommon);
    expect(onEnterSelect).toHaveBeenCalledTimes(1);
    expect(onEnterSelect).toHaveBeenCalledWith(foilCommon);
    expect(onSelect.mock.invocationCallOrder[0]).toBeLessThan(
      onEnterSelect.mock.invocationCallOrder[0],
    );
  });

  it('does not call onEnterSelect for a pointer pick', async () => {
    recordCards([champion, foilCommon]);
    const onEnterSelect = vi.fn<(card: CardSummary) => void>();
    const { user, onSelect } = await renderCombobox({ onEnterSelect });
    await user.type(input(), 'em');
    fireEvent.pointerDown((await screen.findAllByRole('option', {}, LONG))[1]);
    expect(onSelect).toHaveBeenCalledWith(foilCommon);
    expect(onEnterSelect).not.toHaveBeenCalled();
  });

  it('keeps the card name when clearOnSelect is false', async () => {
    recordCards([champion]);
    const { user, onSelect } = await renderCombobox({ clearOnSelect: false });
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    await user.keyboard('{Enter}');
    expect(onSelect).toHaveBeenCalledWith(champion);
    expect(input()).toHaveValue("Ayla, Fury's Champion");
    expect(input()).toHaveAttribute('aria-expanded', 'false');
  });

  it('closes with the first Escape and clears the text with the second', async () => {
    recordCards([champion]);
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(input()).toHaveValue('ay');
    await user.keyboard('{Escape}');
    expect(input()).toHaveValue('');
  });

  it('closes on Tab without selecting', async () => {
    recordCards([champion]);
    const { user, onSelect } = await renderCombobox();
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    await user.tab();
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('selects an option on pointerdown', async () => {
    recordCards([champion, foilCommon]);
    const { user, onSelect } = await renderCombobox();
    await user.type(input(), 'ay');
    const options = await screen.findAllByRole('option', {}, LONG);
    fireEvent.pointerDown(options[1]);
    expect(onSelect).toHaveBeenCalledWith(foilCommon);
  });

  it('closes when the user presses outside', async () => {
    recordCards([champion]);
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(input()).toHaveAttribute('aria-expanded', 'false');
  });

  it('reopens with ArrowDown while the text still has 2 characters', async () => {
    recordCards([champion]);
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    await user.keyboard('{Escape}');
    await user.keyboard('{ArrowDown}');
    expect(await screen.findByRole('listbox')).toBeVisible();
  });
});

describe('CardCombobox states (F2-k S5)', () => {
  it('announces loading, then the number of results and the active card', async () => {
    server.use(
      http.get(`${API}/cards`, async () => {
        await delay(300);
        return HttpResponse.json({
          success: true,
          data: { items: [champion, foilCommon] },
          meta: { ...cardList.meta, per_page: 20, total: 2, pages: 1 },
        });
      }),
    );
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    await waitFor(() => expect(status()).toHaveTextContent('Buscando…'), LONG);
    expect(popupState('loading')).toHaveTextContent('Buscando…');
    await screen.findAllByRole('option', {}, LONG);
    expect(status()).toHaveTextContent('2 resultados');
    expect(status()).toHaveTextContent("Ayla, Fury's Champion");
  });

  it('says there are no results and repeats the query', async () => {
    recordCards([]);
    const { user } = await renderCombobox();
    await user.type(input(), 'zzz');
    await waitFor(
      () => expect(popupState('empty')).toHaveTextContent('No hay cartas que coincidan con «zzz».'),
      LONG,
    );
    expect(status()).toHaveTextContent('No hay cartas que coincidan con «zzz».');
    expect(input()).toHaveAttribute('aria-expanded', 'false'); // no listbox to point at
  });

  it('shows an error state when the search fails', async () => {
    server.use(
      http.get(`${API}/cards`, () =>
        HttpResponse.json({ success: false, error: 'Internal Server Error' }, { status: 500 }),
      ),
    );
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    await waitFor(
      () => expect(popupState('error')).toHaveTextContent('No se pudo buscar. Inténtalo de nuevo.'),
      LONG,
    );
    expect(status()).toHaveTextContent('No se pudo buscar. Inténtalo de nuevo.');
  });

  it('makes no request while offline and nothing is cached', async () => {
    const seen = recordCards();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { user } = await renderCombobox();
    await user.type(input(), 'ay');
    await waitFor(
      () => expect(popupState('offline')).toHaveTextContent('La búsqueda necesita conexión.'),
      LONG,
    );
    expect(status()).toHaveTextContent('La búsqueda necesita conexión.');
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(seen.urls).toHaveLength(0);
  });

  it('is translated to English', async () => {
    recordCards([]);
    const { user } = await renderCombobox({}, 'en');
    await user.type(input(), 'zzz');
    await waitFor(
      () => expect(popupState('empty')).toHaveTextContent('No cards match "zzz".'),
      LONG,
    );
  });
});

describe('CardCombobox accessibility (F2-k AC4)', () => {
  it('has no axe violations with results', async () => {
    recordCards([champion, foilCommon], 35);
    const { user, container } = await renderCombobox();
    await user.type(input(), 'ay');
    await screen.findAllByRole('option', {}, LONG);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no axe violations with no results', async () => {
    recordCards([]);
    const { user, container } = await renderCombobox();
    await user.type(input(), 'zzz');
    await waitFor(() => expect(popupState('empty')).not.toBeNull(), LONG);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no axe violations on error', async () => {
    server.use(
      http.get(`${API}/cards`, () =>
        HttpResponse.json({ success: false, error: 'Internal Server Error' }, { status: 500 }),
      ),
    );
    const { user, container } = await renderCombobox();
    await user.type(input(), 'ay');
    await waitFor(() => expect(popupState('error')).not.toBeNull(), LONG);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('CardCombobox focus (F2-k S1)', () => {
  it('focuses the input on mount with autoFocus', async () => {
    await renderCombobox({ autoFocus: true });
    expect(input()).toHaveFocus();
  });
});
