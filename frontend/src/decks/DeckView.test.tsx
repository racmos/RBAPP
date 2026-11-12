import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { withDecks, withVsCollection } from '@/test/decks';
import { mainCards, rivenDeck } from '@/test/fixtures/decks';
import { signedIn } from '@/test/locations';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const PHONE = 390;

afterEach(() => {
  vi.restoreAllMocks();
  server.events.removeAllListeners();
});

async function openDeck(id: number, width = PHONE) {
  signedIn();
  withDecks();
  const app = await renderApp({ path: `/decks/${id}`, width });
  await screen.findByRole('heading', { level: 1 }, LONG);
  return app;
}

const section = (name: RegExp) =>
  screen.getByText(name, { selector: 'summary *, summary' }).closest('details') as HTMLElement;
const rowNames = (details: HTMLElement) =>
  within(details)
    .getAllByRole('listitem')
    .map((row) => row.querySelector('[data-slot="name"]')?.textContent);

describe('DeckView at 390 px (F5-h stage 1)', () => {
  it('shows the header: name, mode, legality of both modes with every issue explained', async () => {
    await openDeck(41);
    expect(screen.getByRole('heading', { level: 1, name: 'Riven, The Exile' })).toBeVisible();
    expect(document.title).toBe('Riven, The Exile · Rift Manager');
    expect(screen.getByRole('link', { name: 'All decks' })).toHaveAttribute(
      'href',
      '/riftbound/app/decks',
    );
    const legality = screen.getByRole('region', { name: 'Legality' });
    const one = within(legality).getByRole('group', { name: '1v1: Not legal (deck mode)' });
    expect(
      within(one)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['The sideboard has 8 of 10 cards (2 missing).']);
    const two = within(legality).getByRole('group', { name: '2v2: Not legal' });
    expect(
      within(two)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      'The sideboard has 8 of 10 cards (2 missing).',
      "Zhonya's Hourglass is banned in 2v2.",
    ]);
  }, 20000);

  it('shows how complete each section is', async () => {
    await openDeck(41);
    const sections = screen.getByRole('list', { name: 'Sections' });
    expect(
      within(sections)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual([
      'Legend: 1/1',
      'Champion: 1/1',
      'Main deck: 39/39',
      'Runes: 12/12',
      'Battlefields: 3/3',
      'Sideboard: 8/10 (2 missing)',
    ]);
  }, 20000);

  it('lists the sections in order, collapsible, each row with its card facts', async () => {
    await openDeck(41);
    const summaries = Array.from(document.querySelectorAll('details > summary')).map(
      (summary) => summary.textContent,
    );
    expect(summaries).toEqual([
      'Legend1/1',
      'Champion1/1',
      'Main deck39/39',
      'Battlefields3/3',
      'Runes12/12',
      'Sideboard8/10',
    ]);
    expect(screen.queryByText(/Workbench/)).toBeNull();

    const main = section(/^Main deck$/);
    expect(main).toHaveAttribute('open');
    expect(rowNames(main)).toHaveLength(13);
    const rowOf = (name: string) =>
      within(main)
        .getAllByRole('listitem')
        .find(
          (row) => row.querySelector('[data-slot="name"]')?.textContent === name,
        ) as HTMLElement;
    const discipline = rowOf('Discipline');
    expect(within(discipline).getByText('Discipline')).toBeVisible();
    expect(within(discipline).getByText('×3')).toBeVisible();
    expect(within(discipline).getByText('Spell')).toBeVisible();
    expect(within(discipline).getByRole('img', { name: 'Calm' })).toBeVisible();
    expect(within(discipline).getByText('0.25 €')).toBeVisible();
    // the thumbnail is the button that zooms the card
    const thumb = within(discipline).getByRole('button', { name: 'View Discipline' });
    expect(thumb.querySelector('img')).toHaveAttribute('src', mainCards[0].image_src);
    const herder = rowOf('Stellacorn Herder');
    expect(within(herder).getByText('No price')).toBeVisible();

    expect(rowNames(section(/^Legend$/))).toEqual(['Riven, The Exile']);
    expect(rowNames(section(/^Champion$/))).toEqual(['Riven, Broken Blade']);
    expect(within(section(/^Champion$/)).getByText('Champion Unit')).toBeVisible();
    expect(rowNames(section(/^Runes$/))).toEqual(['Chaos Rune', 'Calm Rune']);
    expect(rowNames(section(/^Battlefields$/))).toEqual([
      'Star Spring',
      "Hunters' Circle",
      'Rakelstake',
    ]);

    // a section folds and unfolds
    const summary = main.querySelector('summary') as HTMLElement;
    await userEvent.click(summary);
    expect(main).not.toHaveAttribute('open');
    await userEvent.click(summary);
    expect(main).toHaveAttribute('open');
  }, 20000);

  it('groups the main deck by type with the copies of each, Units first', async () => {
    await openDeck(41);
    const main = section(/^Main deck$/);
    const groups = within(main).getAllByRole('group');
    expect(groups.map((group) => group.querySelector('h3')?.firstChild?.textContent)).toEqual([
      'Unit',
      'Spell',
    ]);
    const copies = groups.map((group) => group.querySelector('h3')?.textContent);
    expect(copies[0]).toMatch(/^Unit\d+ cards?$/);
    expect(rowNames(groups[1] as HTMLElement)).toContain('Discipline');
    // the other sections keep one flat list
    expect(within(section(/^Runes$/)).queryAllByRole('group')).toHaveLength(0);
  }, 20000);

  it('shows energy, power, might and the alt arts on a row, leaving out what a card lacks', async () => {
    await openDeck(41);
    const main = section(/^Main deck$/);
    const rows = within(main).getAllByRole('listitem');
    const find = (name: string) =>
      rows.find(
        (row) => row.querySelector('[data-slot="name"]')?.textContent === name,
      ) as HTMLElement;
    const discipline = find('Discipline');
    expect(within(discipline).getByLabelText('Energy 2')).toHaveTextContent('E2');
    expect(within(discipline).getByLabelText('Power 1')).toHaveTextContent('P1');
    expect(within(discipline).queryByLabelText(/^Might/)).toBeNull();
    expect(within(discipline).getByText('2 alt arts')).toBeVisible();
    const gust = find('Gust');
    expect(gust.querySelector('[data-slot="alt-arts"]')).toBeNull();
    expect(gust.querySelector('[data-slot="energy"]')).toBeNull();
  }, 20000);

  it('has a sticky summary bar with main, runes and legality chips', async () => {
    await openDeck(41);
    const bar = screen.getByRole('region', { name: 'Deck summary' });
    expect(within(bar).getByText('Main 39/39')).toBeVisible();
    expect(within(bar).getByText('Runes 12/12')).toBeVisible();
    expect(within(bar).getByText('1v1: Not legal')).toBeVisible();
    expect(within(bar).getByText('2v2: Not legal')).toBeVisible();
    expect(rivenDeck.value).toBeGreaterThan(0);
    expect(within(bar).getByText(`${rivenDeck.value.toFixed(2)} €`)).toBeVisible();
  }, 20000);

  it('a legal deck says so in both modes', async () => {
    await openDeck(42);
    const legality = screen.getByRole('region', { name: 'Legality' });
    expect(within(legality).getByText('Legal in 1v1.')).toBeVisible();
    expect(within(legality).getByText('Legal in 2v2.')).toBeVisible();
    const sections = screen.getByRole('list', { name: 'Sections' });
    expect(within(sections).getByText('Sideboard: 10/10')).toBeVisible();
  }, 20000);

  it('shows the workbench apart and the cards missing from the catalog', async () => {
    await openDeck(43);
    const bench = section(/^Workbench \(not counted\)$/);
    expect(rowNames(bench)).toEqual(['Baron Nashor']);
    const warning = screen.getByRole('region', { name: 'Cards not in the catalog' });
    expect(within(warning).getByText('OGN-999 (Main deck)')).toBeVisible();
    // empty sections say so
    expect(within(section(/^Legend$/)).getByText('No cards.')).toBeVisible();
  }, 20000);

  it('an unknown deck is a not found page', async () => {
    signedIn();
    withDecks();
    await renderApp({ path: '/decks/999', width: PHONE });
    expect(await screen.findByRole('heading', { name: 'Page not found' }, LONG)).toBeVisible();
  }, 20000);

  it('at 1280 px it shows the same content', async () => {
    await openDeck(41, 1280);
    expect(screen.getByRole('region', { name: 'Legality' })).toBeVisible();
    expect(rowNames(section(/^Main deck$/))).toHaveLength(13);
  }, 20000);

  it('at 390 px there is no card browser pane: one column, the sections open it in a sheet', async () => {
    await openDeck(41);
    await screen.findByRole('button', { name: 'Add cards to the main deck' }, LONG);
    expect(screen.queryByRole('region', { name: 'Card browser' })).toBeNull();
    expect(document.querySelector('[data-layout]')).toHaveAttribute('data-layout', 'single');
  }, 20000);

  it('at 1280 px the editor has two panes: the card browser, then the workspace', async () => {
    await openDeck(41, 1280);
    const browser = await screen.findByRole('region', { name: 'Card browser' }, LONG);
    const page = document.querySelector('[data-layout]') as HTMLElement;
    expect(page).toHaveAttribute('data-layout', 'two-pane');
    const workspace = screen.getByRole('region', { name: 'Deck workspace' });
    expect(
      browser.compareDocumentPosition(workspace) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(within(workspace).getByRole('heading', { level: 1 })).toBeVisible();
    expect(within(workspace).getByRole('region', { name: 'Legality' })).toBeVisible();
    expect(within(workspace).getByRole('list', { name: 'Sections' })).toBeVisible();
    expect(rowNames(section(/^Main deck$/))).toHaveLength(13);
  }, 20000);

  it('at 1280 px offline it stays one column without the browser', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openDeck(41, 1280);
    expect(screen.getByText('Offline: editing is disabled.')).toBeVisible();
    expect(screen.queryByRole('region', { name: 'Card browser' })).toBeNull();
    expect(document.querySelector('[data-layout]')).toHaveAttribute('data-layout', 'single');
  }, 20000);

  it('is axe clean', async () => {
    const { container } = await openDeck(43);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('workspace tabs List / Stats / Collection (F5-i step 4, F5-f)', () => {
  const tabs = () => screen.getByRole('tablist', { name: 'Workspace view' });
  const tab = (name: string) => within(tabs()).getByRole('tab', { name });

  it('opens on List with the deck as before; Stats keeps the header and the summary above', async () => {
    await openDeck(41);
    expect(
      within(tabs())
        .getAllByRole('tab')
        .map((t) => t.textContent),
    ).toEqual(['List', 'Stats', 'Collection']);
    expect(tab('List')).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'List' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Legality' })).toBeVisible();
    expect(rowNames(section(/^Main deck$/))).toHaveLength(13);
    expect(screen.queryByRole('figure', { name: 'Energy curve' })).toBeNull();

    await userEvent.click(tab('Stats'));
    expect(tab('Stats')).toHaveAttribute('aria-selected', 'true');
    expect(tab('List')).toHaveAttribute('aria-selected', 'false');
    const panel = screen.getByRole('tabpanel', { name: 'Stats' });
    expect(within(panel).getByRole('figure', { name: 'Energy curve' })).toBeVisible();
    expect(within(panel).getByText('Main deck', { selector: 'dt' }).nextSibling).toHaveTextContent(
      '39',
    );
    // the list is out of view, the header, save state and summary stay
    expect(screen.queryByRole('region', { name: 'Legality' })).toBeNull();
    expect(screen.queryByRole('list', { name: 'Sections' })).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: 'Riven, The Exile' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Deck summary' })).toBeVisible();
    expect(document.querySelector('[data-slot="save-state"]')).toBeVisible();

    await userEvent.click(tab('List'));
    expect(screen.getByRole('region', { name: 'Legality' })).toBeVisible();
    expect(rowNames(section(/^Main deck$/))).toHaveLength(13);
  }, 20000);

  it('moves between the tabs with the arrow keys, Home and End', async () => {
    // F5-f: Collection is the last tab and reads the deck against the collection
    withVsCollection(() => ({
      missing: [],
      complete: 0,
      names: 0,
      cost_eur: 0,
      owned_value: 0,
      unpriced: 0,
    }));
    await openDeck(41);
    tab('List').focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(tab('Stats')).toHaveFocus();
    expect(tab('Stats')).toHaveAttribute('aria-selected', 'true');
    expect(tab('List')).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('figure', { name: 'Energy curve' })).toBeVisible();
    await userEvent.keyboard('{ArrowRight}');
    expect(tab('Collection')).toHaveFocus();
    expect(tab('Collection')).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{ArrowRight}');
    expect(tab('List')).toHaveFocus();
    expect(tab('List')).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{ArrowLeft}');
    expect(tab('Collection')).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{Home}');
    expect(tab('List')).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{End}');
    expect(tab('Collection')).toHaveFocus();
    expect(screen.getByRole('tabpanel', { name: 'Collection' })).toBeVisible();
  }, 20000);

  it('at 1280 px the tabs sit in the workspace, next to the card browser', async () => {
    await openDeck(41, 1280);
    await screen.findByRole('region', { name: 'Card browser' }, LONG);
    const workspace = screen.getByRole('region', { name: 'Deck workspace' });
    await userEvent.click(within(workspace).getByRole('tab', { name: 'Stats' }));
    expect(within(workspace).getByRole('figure', { name: 'Unit might' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Card browser' })).toBeVisible();
  }, 20000);

  it('is axe clean on the Stats tab', async () => {
    const { container } = await openDeck(41);
    await userEvent.click(tab('Stats'));
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
