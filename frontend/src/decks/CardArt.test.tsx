import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import type { CardSummary, DeckContentV2, DeckDetail } from '@/api/types';
import { cardList, foilCommon as emberWisp } from '@/test/fixtures/cards';
import { recordDeckRequests, withDecks, withPrintings } from '@/test/decks';
import {
  championAlt,
  deckDetail,
  deckDetails,
  disciplineAlts,
  legalDeck,
  line,
  listItemOf,
  mainCards,
  rivenChampion,
  rivenDeck,
} from '@/test/fixtures/decks';
import { renderWithI18n } from '@/test/i18n';
import { signedIn, writes } from '@/test/locations';
import { API, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { CardRow } from './DeckSections';

const LONG = { timeout: 10000 };
const SAVE = { timeout: 5000 };
const PHONE = 390;
const DESKTOP = 1280;

const discipline = mainCards[0];
const [disciplineOgs, disciplineShowcase] = disciplineAlts;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

/** The server saves what it gets and answers the detail of that content. */
function savingServer(details: DeckDetail[]) {
  server.use(
    http.put(`${API}/decks/:id/content`, async ({ params, request }) => {
      const { content } = (await request.json()) as { content: DeckContentV2 };
      const head = details.find((deck) => String(deck.id) === params.id) ?? rivenDeck;
      return ok({ ...deckDetail(head, content), current_seq: head.current_seq });
    }),
  );
}

/** Ember Wisp of the deck's domains, as the browser lists it. */
const wisp: CardSummary = { ...emberWisp, domains: ['Chaos'] };

async function openDeck({
  deck = rivenDeck,
  width = PHONE,
}: { deck?: DeckDetail; width?: number } = {}) {
  signedIn();
  const details = [...deckDetails.filter((d) => d.id !== deck.id), deck];
  withDecks(details.map(listItemOf), details);
  savingServer(details);
  withPrintings([discipline, ...disciplineAlts]);
  server.use(
    http.get(`${API}/cards`, () =>
      HttpResponse.json({
        success: true,
        data: { items: [wisp] },
        meta: { ...cardList.meta, total: 1, pages: 1 },
      }),
    ),
  );
  const sent = recordDeckRequests();
  const app = await renderApp({ path: `/decks/${deck.id}`, width });
  await screen.findByRole('heading', { level: 1 }, LONG);
  // the rule values come from /meta/game: editing starts once they are in
  await waitFor(
    () =>
      expect(
        screen.getAllByRole('button', { name: 'Remove a copy of Discipline' })[0],
      ).toBeEnabled(),
    LONG,
  );
  return { ...app, sent };
}

const section = (name: RegExp) =>
  screen.getByText(name, { selector: 'summary *' }).closest('details') as HTMLElement;
const rowsOf = (details: HTMLElement) =>
  within(details)
    .getAllByRole('listitem')
    .filter((row) => row.querySelector('[data-slot="name"]'));
const rowsNamed = (details: HTMLElement, name: string) =>
  rowsOf(details).filter((row) => row.querySelector('[data-slot="name"]')?.textContent === name);
const printingOf = (row: HTMLElement) =>
  row.querySelector('[data-slot="printing"]')?.textContent ?? null;
const qtyOf = (row: HTMLElement) =>
  row.querySelector('[data-slot="qty"]')?.textContent?.replace('×', '');
const puts = (sent: ReturnType<typeof recordDeckRequests>, id = 41) =>
  writes(sent).filter(
    (request) => request.method === 'PUT' && request.path === `/decks/${id}/content`,
  );
const sentContent = (sent: ReturnType<typeof recordDeckRequests>, id = 41) =>
  (puts(sent, id).at(-1)?.body as { content: DeckContentV2 }).content;

describe('Card zoom: a deck row (owner request 1)', () => {
  it('the thumbnail opens the full card; Escape and Close close it and focus the thumb', async () => {
    await openDeck();
    const thumb = screen.getByRole('button', { name: 'View Discipline' });
    await userEvent.click(thumb);
    let zoom = await screen.findByRole('dialog', { name: 'Discipline' });
    expect(within(zoom).getByRole('img', { name: 'Discipline' })).toHaveAttribute(
      'src',
      discipline.image_src,
    );
    expect(within(zoom).getByText('OGN-310')).toBeVisible();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Discipline' })).toBeNull();
    expect(thumb).toHaveFocus();

    await userEvent.click(thumb);
    zoom = await screen.findByRole('dialog', { name: 'Discipline' });
    await userEvent.click(within(zoom).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog', { name: 'Discipline' })).toBeNull();
    expect(thumb).toHaveFocus();
    // the row keeps its own controls
    expect(screen.getByRole('button', { name: 'Remove a copy of Discipline' })).toBeEnabled();
  }, 20000);

  it('a card without an image zooms to its placeholder and name', async () => {
    const deck: DeckDetail = {
      ...rivenDeck,
      cards: { ...rivenDeck.cards, [discipline.key]: { ...discipline, image_src: null } },
    };
    await openDeck({ deck });
    await userEvent.click(screen.getByRole('button', { name: 'View Discipline' }));
    const zoom = await screen.findByRole('dialog', { name: 'Discipline' });
    expect(within(zoom).getByRole('img', { name: 'Discipline' }).tagName).toBe('DIV');
    expect(within(zoom).getByRole('heading', { name: 'Discipline' })).toBeVisible();
  }, 20000);

  it('is axe clean open at 390 and at 1280', async () => {
    for (const width of [PHONE, DESKTOP]) {
      const { unmount } = await openDeck({ width });
      await userEvent.click(screen.getByRole('button', { name: 'View Discipline' }));
      const zoom = await screen.findByRole('dialog', { name: 'Discipline' });
      expect(await axe(zoom)).toHaveNoViolations();
      unmount();
    }
  }, 40000);
});

describe('Card zoom: a card browser tile', () => {
  it('the magnifier opens the card and never adds it', async () => {
    const { sent } = await openDeck({ width: DESKTOP });
    const browser = await screen.findByRole('region', { name: 'Card browser' }, LONG);
    const add = await within(browser).findByRole('button', { name: 'Add Ember Wisp' }, LONG);
    const view = within(browser).getByRole('button', { name: 'View Ember Wisp' });
    // a sibling of the tile, never a button inside a button
    expect(add.contains(view)).toBe(false);
    await userEvent.click(view);
    const zoom = await screen.findByRole('dialog', { name: 'Ember Wisp' });
    expect(within(zoom).getByText(wisp.key)).toBeVisible();
    await userEvent.click(within(zoom).getByRole('button', { name: 'Close' }));
    expect(view).toHaveFocus();
    await new Promise((resolve) => window.setTimeout(resolve, 1300));
    expect(puts(sent)).toEqual([]);
    expect(add.querySelector('[data-slot="copies"]')).toBeNull();
    // the tile itself still adds
    await userEvent.click(add);
    await waitFor(() => expect(puts(sent)).toHaveLength(1), SAVE);
  }, 30000);

  it('in the phone sheet, closing the zoom keeps the sheet open', async () => {
    await openDeck();
    await userEvent.click(screen.getByRole('button', { name: 'Add cards to the main deck' }));
    const sheet = await screen.findByRole('dialog', { name: 'Add to Main deck' });
    await userEvent.click(
      await within(sheet).findByRole('button', { name: 'View Ember Wisp' }, LONG),
    );
    await screen.findByRole('dialog', { name: 'Ember Wisp' });
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Ember Wisp' })).toBeNull();
    expect(screen.getByRole('dialog', { name: 'Add to Main deck' })).toBeVisible();
  }, 30000);
});

describe('Art switch (owner request 2)', () => {
  it('moves copies of a line to other printings; the total stays and the deck saves it', async () => {
    const { sent } = await openDeck();
    const main = section(/^Main deck$/);
    await userEvent.click(screen.getByRole('button', { name: 'Change art of Discipline' }));
    const dialog = await screen.findByRole('dialog', {
      name: 'Choose art for Discipline (Main deck)',
    });
    const item = async (code: string) =>
      (await within(dialog).findByText(code, {}, LONG)).closest('li') as HTMLElement;
    const ogs = await item('OGS-7');
    const source = await item('OGN-310');
    const showcase = await item('OGN-310a');
    expect(within(ogs).getByText('You own 2')).toBeVisible();
    expect(within(ogs).getByText('2.00 €')).toBeVisible();
    expect(within(showcase).getByText('Showcase')).toBeVisible();
    expect(within(source).getByText('3 copies')).toBeVisible();
    expect(within(ogs).getByText('0 copies')).toBeVisible();
    // nothing can leave a printing with no copies
    expect(within(ogs).getByRole('button', { name: 'One less copy in OGS-7' })).toBeDisabled();

    const more = (code: string) =>
      within(dialog).getByRole('button', { name: `One more copy in ${code}` });
    await userEvent.click(more('OGS-7'));
    await userEvent.click(more('OGS-7'));
    await userEvent.click(more('OGN-310a'));
    // every copy is taken: the source has none left to give
    expect(within(source).getByText('0 copies')).toBeVisible();
    expect(more('OGS-7')).toBeDisabled();
    expect(more('OGS-7')).toHaveAccessibleDescription('OGN-310 has no copies left to move.');
    await userEvent.click(
      within(dialog).getByRole('button', { name: 'One less copy in OGN-310a' }),
    );
    expect(within(source).getByText('1 copy')).toBeVisible();
    expect(within(dialog).getByText('This section keeps 3 copies of Discipline.')).toBeVisible();
    // nothing changed in the deck until Apply
    expect(rowsNamed(main, 'Discipline')).toHaveLength(1);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }));

    expect(screen.queryByRole('dialog', { name: /^Choose art/ })).toBeNull();
    const rows = rowsNamed(main, 'Discipline');
    expect(rows.map(printingOf)).toEqual(['OGN-310', 'OGS-7']);
    expect(rows.map(qtyOf)).toEqual(['1', '2']);
    expect(rows[1].querySelector('img')).toHaveAttribute('src', disciplineOgs.image_src);
    expect(within(main).getByText('39/39')).toBeVisible();
    expect(
      (await screen.findAllByText('Art of Discipline changed.', {}, LONG)).length,
    ).toBeGreaterThan(0);

    await waitFor(() => expect(puts(sent)).toHaveLength(1), SAVE);
    const body = sentContent(sent);
    expect(body.main.slice(0, 2)).toEqual([
      { set: 'OGN', id: '310', qty: 1 },
      { set: 'OGS', id: '7', qty: 2 },
    ]);
    expect(body.main.reduce((n, l) => n + l.qty, 0)).toBe(39);
    expect(disciplineShowcase.key).toBe('OGN-310a');
  }, 30000);

  it('Undo puts the printings back', async () => {
    await openDeck();
    const main = section(/^Main deck$/);
    await userEvent.click(screen.getByRole('button', { name: 'Change art of Discipline' }));
    const dialog = await screen.findByRole('dialog', { name: /^Choose art for Discipline/ });
    await userEvent.click(
      await within(dialog).findByRole('button', { name: 'One more copy in OGS-7' }, LONG),
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }));
    expect(rowsNamed(main, 'Discipline')).toHaveLength(2);
    await screen.findAllByText('Art of Discipline changed.', {}, LONG);
    // the newest toast (an earlier test may leave its own)
    const undo = screen.getAllByRole('button', { name: 'Undo' }).at(-1) as HTMLElement;
    await userEvent.click(undo);
    const rows = rowsNamed(main, 'Discipline');
    expect(rows.map(qtyOf)).toEqual(['3']);
  }, 30000);

  it('Cancel changes nothing', async () => {
    const { sent } = await openDeck();
    await userEvent.click(screen.getByRole('button', { name: 'Change art of Discipline' }));
    const dialog = await screen.findByRole('dialog', { name: /^Choose art for Discipline/ });
    await userEvent.click(
      await within(dialog).findByRole('button', { name: 'One more copy in OGS-7' }, LONG),
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(rowsNamed(section(/^Main deck$/), 'Discipline').map(qtyOf)).toEqual(['3']);
    expect(screen.getByRole('button', { name: 'Change art of Discipline' })).toHaveFocus();
    await new Promise((resolve) => window.setTimeout(resolve, 1300));
    // (an earlier test may still flush its own content on unmount: none of it is this change)
    const sentArts = puts(sent).flatMap((r) =>
      (r.body as { content: DeckContentV2 }).content.main.filter((l) => l.set === 'OGS'),
    );
    expect(sentArts).toEqual([]);
  }, 30000);

  it('the champion slot chooses one printing', async () => {
    const champion = { ...rivenChampion, variants: 2 };
    const deck: DeckDetail = {
      ...rivenDeck,
      cards: { ...rivenDeck.cards, [champion.key]: champion },
    };
    const { sent } = await openDeck({ deck });
    withPrintings([champion, championAlt]);
    await userEvent.click(
      screen.getByRole('button', { name: 'Change art of Riven, Broken Blade' }),
    );
    const dialog = await screen.findByRole('dialog', {
      name: 'Choose art for Riven, Broken Blade (Champion)',
    });
    const current = await within(dialog).findByRole('radio', { name: /OGN-301/ }, LONG);
    expect(current).toBeChecked();
    await userEvent.click(within(dialog).getByRole('radio', { name: /OGS-20/ }));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Apply' }));
    const row = rowsNamed(section(/^Champion$/), 'Riven, Broken Blade')[0];
    expect(printingOf(row)).toBe('OGS-20');
    await waitFor(() => expect(puts(sent)).toHaveLength(1), SAVE);
    expect(sentContent(sent).champion).toEqual({ set: 'OGS', id: '20' });
    expect(sentContent(sent).main).toEqual(rivenDeck.content.main);
  }, 30000);

  it('offline the badge is disabled with the reason', async () => {
    signedIn();
    withDecks();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderApp({ path: '/decks/41', width: PHONE });
    await screen.findByRole('heading', { level: 1 }, LONG);
    const change = screen.getByRole('button', { name: 'Change art of Discipline' });
    expect(change).toBeDisabled();
    expect(change).toHaveAccessibleDescription('Offline: the art cannot be changed.');
  }, 20000);

  it('a read-only row keeps a plain badge (no editor), and still zooms', async () => {
    await renderWithI18n(
      <ul>
        <CardRow card={discipline} qty={3} zone="main" />
      </ul>,
    );
    expect(screen.queryByRole('button', { name: /^Change art/ })).toBeNull();
    expect(screen.getByText('2 alt arts')).toBeVisible();
    expect(screen.getByRole('button', { name: 'View Discipline' })).toBeVisible();
  });

  it('is axe clean open at 390 and at 1280', async () => {
    for (const width of [PHONE, DESKTOP]) {
      const { unmount } = await openDeck({ width });
      await userEvent.click(screen.getByRole('button', { name: 'Change art of Discipline' }));
      const dialog = await screen.findByRole('dialog', { name: /^Choose art for Discipline/ });
      await within(dialog).findByText('OGS-7', {}, LONG);
      expect(await axe(dialog)).toHaveNoViolations();
      unmount();
    }
  }, 40000);
});

describe('Several printings of one card (owner request 3)', () => {
  /** The legal deck with its 3 Discipline in 3 printings, the two alt arts listed last. */
  const threeArts = deckDetail(
    { id: 44, name: 'Three arts', mode: '2v2' },
    {
      ...legalDeck.content,
      main: [
        ...legalDeck.content.main.map((l) =>
          l.set === discipline.set_id && l.id === discipline.card_id ? line(discipline, 1) : l,
        ),
        line(disciplineOgs, 1),
        line(disciplineShowcase, 1),
      ],
    },
  );

  it('shows 3 rows of 1, side by side with their printing; the deck stays legal', async () => {
    await openDeck({ deck: threeArts });
    const main = section(/^Main deck$/);
    const rows = rowsOf(main);
    const names = rows.map((row) => row.querySelector('[data-slot="name"]')?.textContent);
    const first = names.indexOf('Discipline');
    expect(names.slice(first, first + 3)).toEqual(['Discipline', 'Discipline', 'Discipline']);
    const arts = rowsNamed(main, 'Discipline');
    expect(arts.map(printingOf)).toEqual(['OGN-310', 'OGN-310a', 'OGS-7']);
    expect(arts.map(qtyOf)).toEqual(['1', '1', '1']);
    expect(within(main).getByText('39/39')).toBeVisible();
    // a name with one printing and no alt art shows no code
    expect(printingOf(rowsNamed(main, 'Traveling Merchant')[0])).toBeNull();
    const legality = screen.getByRole('region', { name: 'Legality' });
    expect(within(legality).getByText('Legal in 1v1.')).toBeVisible();
    expect(within(legality).getByText('Legal in 2v2.')).toBeVisible();
    // the copies count by name: a 4th, in any printing, is refused
    const adds = screen.getAllByRole('button', { name: 'Add a copy of Discipline' });
    expect(adds).toHaveLength(3);
    for (const add of adds) {
      expect(add).toBeDisabled();
      expect(add).toHaveAccessibleDescription('Discipline has 4 copies (max 3).');
    }
  }, 20000);
});
