import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { withDecks } from '@/test/decks';
import { rivenDeck } from '@/test/fixtures/decks';
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
    const discipline = within(main).getAllByRole('listitem')[0];
    expect(within(discipline).getByText('Discipline')).toBeVisible();
    expect(within(discipline).getByText('×3')).toBeVisible();
    expect(within(discipline).getByText('Spell')).toBeVisible();
    expect(within(discipline).getByRole('img', { name: 'Calm' })).toBeVisible();
    expect(within(discipline).getByText('0.25 €')).toBeVisible();
    expect(within(discipline).getByRole('img', { name: 'Discipline' })).toBeInTheDocument();
    const herder = within(main).getAllByRole('listitem')[4];
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

  it('is axe clean', async () => {
    const { container } = await openDeck(43);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
