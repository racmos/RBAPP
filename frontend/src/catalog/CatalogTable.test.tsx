import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';
import { API, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

describe('CatalogTable (F2-i S4)', () => {
  it('renders 13 columns at 1024 px inside a horizontal scroll wrapper', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1024 });
    const table = await screen.findByRole('table', {}, LONG);
    const headers = screen.getAllByRole('columnheader');
    expect(headers).toHaveLength(13);
    expect(table.parentElement!.tagName).toBe('DIV');
  });

  it('renders 16 columns at 1280 px', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('table', {}, LONG);
    expect(screen.getAllByRole('columnheader')).toHaveLength(16);
  });

  it('sets aria-sort on the active column and toggles direction', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards?sort=name', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    const nameHeader = await within(table).findByRole('columnheader', { name: /Name/ });
    expect(nameHeader).toHaveAttribute('aria-sort', 'ascending');
    await userEvent.click(within(table).getByRole('button', { name: /Name/ }));
    await waitFor(() => expect(nameHeader).toHaveAttribute('aria-sort', 'descending'));
  });

  it('starts price sort in descending order', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    await userEvent.click(within(table).getByRole('button', { name: /Price/ }));
    await waitFor(() => expect(where()).toBe('/cards?sort=price&dir=desc'), LONG);
  });

  it('starts 7-day trend sort in descending order', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    const { where } = await renderApp({ path: '/cards', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    await userEvent.click(within(table).getByRole('button', { name: /7 d/ }));
    await waitFor(() => expect(where()).toBe('/cards?sort=trend_7d&dir=desc'), LONG);
  });

  it('name links point to the detail route', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    const table = await screen.findByRole('table', {}, LONG);
    const link = await within(table).findByRole('link', { name: /Ayla/ });
    expect(link).toHaveAttribute('href', '/riftbound/app/cards/OGN/79');
  });

  it('falls back from stored table to list below 860 px', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 390 });
    expect(await screen.findByRole('list', { name: 'Results' }, LONG)).toBeVisible();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});

describe('CatalogTable single scroll (owner feedback S22)', () => {
  const css = readCss(join(SRC_DIR, 'catalog/CatalogTable.module.css'));
  const pageCss = readCss(join(SRC_DIR, 'catalog/CatalogPage.module.css'));

  it('≥ 1240 px the table scrolls with the page: no box with its own scrollbar', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1440 });
    const table = await screen.findByRole('table', {}, LONG);
    const box = table.parentElement!;
    expect(box.dataset.slot).toBe('table-scroll');
    expect(box).toHaveAttribute('data-fit');
    // no fixed minimum: the columns wrap to the width of the results column
    expect(box.className).not.toMatch(/scrollWrap/);
  });

  it('below 1240 px the 13 columns keep their horizontal scroll box', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1024 });
    const box = (await screen.findByRole('table', {}, LONG)).parentElement!;
    expect(box).not.toHaveAttribute('data-fit');
    expect(box.className).toMatch(/scrollWrap/);
  });

  it('fitted, long cells wrap and the numbers keep to one line', () => {
    expect(declsFor(css, '.fit .td')).toContainEqual({ prop: 'padding', value: '6px' });
    expect(declsFor(css, '.fit .th')).toContainEqual({ prop: 'padding', value: '6px' });
    expect(declsFor(css, '.fit .nameCell')).toContainEqual({ prop: 'min-width', value: '0' });
    expect(declsFor(css, '.right')).toContainEqual({ prop: 'white-space', value: 'nowrap' });
  });

  it('fitted, a price and its trend stack instead of widening the column', () => {
    expect(declsFor(css, '.fit .priceCell > *')).toContainEqual({
      prop: 'flex-wrap',
      value: 'wrap',
    });
  });

  it('the tags, foil and 30 d columns give way when the results column is narrow', async () => {
    expect(declsFor(css, '.fit')).toContainEqual({ prop: 'container-type', value: 'inline-size' });
    const narrow = rules(css).find(
      (rule) =>
        rule.selectors.includes('.optional') &&
        rule.atRules.some((at) => /^container \(max-width: \d+px\)$/.test(at)),
    );
    expect(narrow?.decls).toContainEqual({ prop: 'display', value: 'none' });
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1280 });
    await screen.findByRole('table', {}, LONG);
    const optional = screen
      .getAllByRole('columnheader')
      .filter((th) => /optional/.test(th.className))
      .map((th) => th.textContent);
    expect(optional).toEqual(['Tags', 'Foil', '30 d']);
  });

  it('in table view the page takes the wide width from 1240 px', async () => {
    const wide = rules(pageCss).find(
      (rule) =>
        rule.selectors.includes(".page[data-view='table']") &&
        rule.atRules.includes('media (min-width: 1240px)'),
    );
    expect(wide?.decls).toContainEqual({ prop: 'max-width', value: 'var(--maxw-wide)' });
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    const { container } = await renderApp({ path: '/cards', width: 1440 });
    await screen.findByRole('table', {}, LONG);
    const page = container.querySelector('[data-view="table"]');
    expect(page).toHaveAttribute('data-width', 'wide');
  });

  it('in grid view the page keeps the regular width', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards', width: 1440 });
    await screen.findByRole('link', { name: /Ayla/ }, LONG);
    expect(container.querySelector('[data-width="wide"]')).toBeNull();
  });
});
