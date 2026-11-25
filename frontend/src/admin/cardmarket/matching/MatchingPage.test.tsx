import { join } from 'node:path';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { callsTo, linkList, matchingApi } from '@/test/fixtures/cardmarketMatching';

const LONG = { timeout: 10000 };
const PATH = '/admin/cardmarket/matching';

async function openPage(path = PATH, width = 1280) {
  const rendered = await renderApp({ path, width });
  await screen.findByRole('heading', { name: 'Matching workbench', level: 1 }, LONG);
  return rendered;
}

afterEach(() => {
  vi.restoreAllMocks();
  // the toast store outlives a render: an Undo left by one test must not reach the next
  clearToasts();
});

const TAB_NAMES = ['Prepare', 'Auto-match', 'To link', 'Linked'];

const tabNames = () =>
  within(screen.getByRole('tablist', { name: 'Matching sections' }))
    .getAllByRole('tab')
    .map((tab) => tab.textContent);

const selected = (name: string) =>
  vi.waitFor(() =>
    expect(screen.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true'),
  );

describe('MatchingPage frame (CM-b, CM-l)', () => {
  it('shows the counters of the status and the four tabs in workflow order, To link selected', async () => {
    matchingApi();
    await openPage();
    expect(await screen.findByText('Unmatched products: 305', undefined, LONG)).toBeVisible();
    // CM-d, CM-l: the expansions counter opens the Expansions view of Prepare
    expect(screen.getByRole('link', { name: 'Unmapped expansions: 2' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cardmarket/matching?tab=prepare&view=expansions',
    );
    expect(tabNames()).toEqual(TAB_NAMES);
    const tab = screen.getByRole('tab', { name: 'To link' });
    expect(tab).toHaveAttribute('aria-selected', 'true');
    expect(tab).toHaveAttribute('id', 'matching-tab-link');
    expect(tab).toHaveAttribute('aria-controls', 'matching-panel-link');
    const panel = screen.getByRole('tabpanel', { name: 'To link' });
    expect(panel).toHaveAttribute('id', 'matching-panel-link');
    expect(screen.getByRole('link', { name: 'Back to Cardmarket' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cardmarket',
    );
  });

  it('shows the same four tabs on a 360 px phone', async () => {
    matchingApi();
    await openPage(PATH, 360);
    expect(tabNames()).toEqual(TAB_NAMES);
    expect(screen.getByRole('tab', { name: 'To link' })).toHaveAttribute('aria-selected', 'true');
  });

  it('arrow keys, Home and End move between the four tabs and the tab goes to the URL', async () => {
    matchingApi();
    const { where } = await openPage();
    (await screen.findByRole('tab', { name: 'To link' }, LONG)).focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Linked' })).toHaveFocus();
    await selected('Linked');
    expect(where()).toBe(`${PATH}?tab=linked`);
    // from the last tab ArrowRight wraps to the first
    await userEvent.keyboard('{ArrowRight}');
    await selected('Prepare');
    expect(screen.getByRole('tab', { name: 'Prepare' })).toHaveFocus();
    expect(screen.getByRole('tab', { name: 'Prepare' })).toHaveAttribute(
      'id',
      'matching-tab-prepare',
    );
    expect(screen.getByRole('tabpanel', { name: 'Prepare' })).toHaveAttribute(
      'id',
      'matching-panel-prepare',
    );
    expect(where()).toBe(`${PATH}?tab=prepare`);
    await userEvent.keyboard('{ArrowRight}');
    await selected('Auto-match');
    expect(where()).toBe(`${PATH}?tab=auto`);
    await userEvent.keyboard('{End}');
    await selected('Linked');
    await userEvent.keyboard('{Home}');
    await selected('Prepare');
    await userEvent.keyboard('{ArrowLeft}');
    await selected('Linked');
    await userEvent.keyboard('{ArrowLeft}');
    await selected('To link');
    expect(where()).toBe(PATH);
  });

  it('switching tab drops the filters of the previous one', async () => {
    matchingApi();
    const { where } = await openPage(`${PATH}?q=ahri&type=single`);
    await userEvent.click(await screen.findByRole('tab', { name: 'Linked' }, LONG));
    expect(where()).toBe(`${PATH}?tab=linked`);
  });

  it('keeps the tabs on one row on phones, scrolling inside their bar only', () => {
    const css = readCss(join(SRC_DIR, 'admin/cardmarket/matching/MatchingPage.module.css'));
    const tabs = declsFor(css, '.tabs');
    expect(tabs).toContainEqual({ prop: 'flex-wrap', value: 'nowrap' });
    expect(tabs).toContainEqual({ prop: 'overflow-x', value: 'auto' });
    // the phone padding of a tab is small enough for four tabs at 360 px; desktop widens it
    expect(declsFor(css, '.tab')).toContainEqual({ prop: 'padding', value: '8px 10px' });
  });
});

describe('Prepare tab: Expansions | Missing cards (CM-l S2)', () => {
  it('opens on Expansions and switches to Missing cards through the view in the URL', async () => {
    const calls = matchingApi();
    const user = userEvent.setup();
    const { where } = await openPage(`${PATH}?tab=prepare`);
    const views = await screen.findByRole('radiogroup', { name: 'Prepare view' }, LONG);
    expect(
      within(views)
        .getAllByRole('radio')
        .map((radio) => radio.closest('label')?.textContent),
    ).toEqual(['Expansions', 'Missing cards']);
    expect(within(views).getByRole('radio', { name: 'Expansions' })).toBeChecked();
    expect(await screen.findByRole('table', { name: 'Cardmarket expansions' }, LONG)).toBeVisible();
    await user.click(within(views).getByRole('radio', { name: 'Missing cards' }));
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=prepare&view=missing`));
    expect(await screen.findByRole('combobox', { name: 'Promo set' }, LONG)).toBeVisible();
    expect(screen.queryByRole('table', { name: 'Cardmarket expansions' })).toBeNull();
    expect(callsTo(calls, 'GET', '/promo-cards').length).toBeGreaterThan(0);
  });

  it('keeps set= for Missing cards', async () => {
    const calls = matchingApi();
    await openPage(`${PATH}?tab=prepare&view=missing&set=OGNX`);
    expect(await screen.findByRole('table', { name: 'Missing promo cards' }, LONG)).toBeVisible();
    expect(screen.getByRole('radio', { name: 'Missing cards' })).toBeChecked();
    expect(callsTo(calls, 'GET', '/promo-cards').map((call) => call.search.toString())).toContain(
      'set=OGNX',
    );
  });

  it('changing the view keeps set and drops the other filters and the page (S6)', async () => {
    matchingApi();
    const user = userEvent.setup();
    const { where } = await openPage(`${PATH}?tab=prepare&view=missing&set=OGNX&printings=RAD`);
    await user.click(await screen.findByRole('radio', { name: 'Expansions' }, LONG));
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=prepare&view=expansions&set=OGNX`));
  });
});

describe('To link tab: To link | Ignored (CM-l S3)', () => {
  it('shows the ignored count in its label and opens the Ignored list, keeping q', async () => {
    matchingApi();
    const user = userEvent.setup();
    const { where } = await openPage(`${PATH}?q=ahri&type=single&page=2`);
    const views = await screen.findByRole('radiogroup', { name: 'To link view' }, LONG);
    expect(within(views).getByRole('radio', { name: 'To link' })).toBeChecked();
    const ignored = await within(views).findByRole('radio', { name: 'Ignored 1' }, LONG);
    await user.click(ignored);
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?view=ignored&q=ahri`));
    expect(await screen.findByRole('table', { name: 'Ignored products' }, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Restore Token Pack' })).toBeVisible();
    expect(screen.getByRole('tab', { name: 'To link' })).toHaveAttribute('aria-selected', 'true');
    await user.click(screen.getByRole('radio', { name: 'To link' }));
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?q=ahri`));
    expect(await screen.findByRole('list', { name: 'Products to link' }, LONG)).toBeVisible();
  });

  it('an empty ignore list shows 0 in the label', async () => {
    matchingApi({ ignored: [] });
    await openPage();
    expect(await screen.findByRole('radio', { name: 'Ignored 0' }, LONG)).toBeVisible();
  });
});

describe('Linked tab: All links | Conflicts (CM-l S4)', () => {
  it('shows the conflict count in warning tone and opens the conflicts, keeping q and set', async () => {
    matchingApi();
    const user = userEvent.setup();
    const { where } = await openPage(`${PATH}?tab=linked&q=9&set=OGN&foil=N&page=2`);
    const views = await screen.findByRole('radiogroup', { name: 'Linked view' }, LONG);
    expect(within(views).getByRole('radio', { name: 'All links' })).toBeChecked();
    const conflicts = await within(views).findByRole('radio', { name: 'Conflicts 2' }, LONG);
    expect(conflicts.closest('label')!.querySelector('[data-count]')).toHaveAttribute(
      'data-tone',
      'warning',
    );
    await user.click(conflicts);
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=linked&view=conflicts&q=9&set=OGN`));
    expect(await screen.findByRole('list', { name: 'Conflict slots' }, LONG)).toBeVisible();
    await user.click(screen.getByRole('radio', { name: 'All links' }));
    await vi.waitFor(() => expect(where()).toBe(`${PATH}?tab=linked&q=9&set=OGN`));
    expect(await screen.findByRole('table', { name: 'Cardmarket links' }, LONG)).toBeVisible();
  });

  it('without conflicts the label reads 0 in the plain tone', async () => {
    matchingApi({ conflicts: linkList([]) });
    await openPage(`${PATH}?tab=linked`);
    const conflicts = await screen.findByRole('radio', { name: 'Conflicts 0' }, LONG);
    expect(conflicts.closest('label')!.querySelector('[data-count]')).toHaveAttribute(
      'data-tone',
      'neutral',
    );
  });
});

describe('old tab URLs (CM-l S5)', () => {
  const ALIASES: [string, string, string, string | null][] = [
    ['?tab=conflicts', '?tab=linked&view=conflicts', 'Linked', 'Conflicts 2'],
    ['?tab=ignored&q=ahri', '?view=ignored&q=ahri', 'To link', 'Ignored 1'],
    ['?tab=expansions&show=all', '?tab=prepare&view=expansions&show=all', 'Prepare', 'Expansions'],
    ['?tab=missing&set=OGNX', '?tab=prepare&view=missing&set=OGNX', 'Prepare', 'Missing cards'],
    ['?tab=nope&q=ahri', '?q=ahri', 'To link', 'To link'],
  ];

  it.each(ALIASES)('%s lands on %s with a replace', async (old, now, tab, view) => {
    matchingApi();
    const { where, router } = await openPage(`${PATH}${old}`);
    await vi.waitFor(() => expect(where()).toBe(`${PATH}${now}`));
    expect(router.state.historyAction).toBe('REPLACE');
    await selected(tab);
    if (view) expect(await screen.findByRole('radio', { name: view }, LONG)).toBeChecked();
  });

  it.each([
    ['?tab=auto', 'Auto-match'],
    ['?tab=linked&q=900', 'Linked'],
  ])('%s is kept as it is', async (search, tab) => {
    matchingApi();
    const { where, router } = await openPage(`${PATH}${search}`);
    await selected(tab);
    expect(where()).toBe(`${PATH}${search}`);
    expect(router.state.historyAction).toBe('POP');
  });
});

describe('every old action stays within two clicks (CM-l S8)', () => {
  it('reaches Ignore, Restore, Relink, Unlink, conflicts, preview, map, view products and missing cards', async () => {
    matchingApi();
    const user = userEvent.setup();
    await openPage();
    // To link: Ignore, no click
    expect(
      (await screen.findAllByRole('button', { name: /^Ignore/ }, LONG)).length,
    ).toBeGreaterThan(0);
    // Ignored: Restore, one click
    await user.click(await screen.findByRole('radio', { name: 'Ignored 1' }, LONG));
    expect(await screen.findByRole('button', { name: 'Restore Token Pack' }, LONG)).toBeVisible();
    // Linked: Relink and Unlink, one click
    await user.click(screen.getByRole('tab', { name: 'Linked' }));
    expect(await screen.findByRole('button', { name: 'Relink Product 601' }, LONG)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Unlink Product 601' })).toBeVisible();
    // Conflicts: two clicks
    await user.click(await screen.findByRole('radio', { name: 'Conflicts 2' }, LONG));
    expect(await screen.findByRole('button', { name: 'Unlink Product 702' }, LONG)).toBeVisible();
    // Auto-match: preview, one click
    await user.click(screen.getByRole('tab', { name: 'Auto-match' }));
    expect(await screen.findByRole('button', { name: 'Preview' }, LONG)).toBeVisible();
    // Prepare: map an expansion and view its products, one click
    await user.click(screen.getByRole('tab', { name: 'Prepare' }));
    const table = await screen.findByRole('table', { name: 'Cardmarket expansions' }, LONG);
    expect(
      within(table).getAllByRole('button', { name: /^Map .* to a set$/ }).length,
    ).toBeGreaterThan(0);
    expect(
      within(table).getAllByRole('button', { name: /^View the products of/ }).length,
    ).toBeGreaterThan(0);
    // Missing cards: two clicks
    await user.click(screen.getByRole('radio', { name: 'Missing cards' }));
    expect(await screen.findByRole('combobox', { name: 'Promo set' }, LONG)).toBeVisible();
  }, 20000);
});

describe('accessibility of the four tabs (CM-l S7)', () => {
  const READY: [string, () => Promise<unknown>][] = [
    [
      `${PATH}?tab=prepare`,
      () => screen.findByRole('table', { name: 'Cardmarket expansions' }, LONG),
    ],
    [`${PATH}?tab=auto`, () => screen.findByRole('list', { name: 'Products to review' }, LONG)],
    [PATH, () => screen.findByRole('list', { name: 'Products to link' }, LONG)],
    [`${PATH}?tab=linked`, () => screen.findByRole('table', { name: 'Cardmarket links' }, LONG)],
  ];

  it.each([1280, 360])(
    'has no axe violations on any tab at %i px',
    async (width) => {
      for (const [path, ready] of READY) {
        matchingApi();
        const page = await openPage(path, width);
        await ready();
        expect(await axe(page.container), path).toHaveNoViolations();
        page.unmount();
      }
    },
    40000,
  );

  it('at 390 the computer hint shows', async () => {
    matchingApi();
    await openPage(PATH, 390);
    await screen.findByRole('list', { name: 'Products to link' }, LONG);
    expect(screen.getByText(/easier on a computer/i)).toBeVisible();
  });
});

describe('MatchingPage admin frame (CM-b)', () => {
  it('the admin select on tablets shows Cardmarket for the workbench', async () => {
    matchingApi();
    await openPage(PATH, 1000);
    const select = screen.getByRole('combobox', { name: 'Administration sections' });
    expect(select).toHaveValue('/admin/cardmarket');
  });

  it('the side navigation marks Cardmarket as the current section', async () => {
    matchingApi();
    await openPage();
    const nav = screen.getByRole('navigation', { name: 'Administration sections' });
    expect(within(nav).getByRole('link', { name: 'Cardmarket' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('a signed-in non-admin lands on the 404 view', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: PATH, width: 1280 });
    expect(await screen.findByRole('heading', { name: 'Page not found' }, LONG)).toBeVisible();
  });
});

describe('Cardmarket page links to the workbench (CM-b)', () => {
  it('the unmatched counter and a Matching workbench link open the workbench', async () => {
    matchingApi();
    server.use(
      http.get(`${API}/admin/cardmarket/loads`, () => ok({ items: [] })),
      http.get(`${API}/admin/jobs`, () => ok({ items: [] })),
    );
    const { where } = await renderApp({ path: '/admin/cardmarket', width: 1280 });
    const header = await screen.findByRole('region', { name: 'Status' }, LONG);
    const counter = await within(header).findByRole('link', {
      name: 'Unmatched products: 305',
    });
    expect(counter).toHaveAttribute('href', '/riftbound/app/admin/cardmarket/matching?type=single');
    expect(screen.getByRole('link', { name: 'Matching workbench' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cardmarket/matching',
    );
    await userEvent.click(counter);
    expect(
      await screen.findByRole('heading', { name: 'Matching workbench', level: 1 }, LONG),
    ).toBeVisible();
    expect(where()).toBe(`${PATH}?type=single`);
  });
});
