import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { clearToasts } from '@/components/ui/toastStore';
import { matchingApi } from '@/test/fixtures/cardmarketMatching';

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

describe('MatchingPage frame (CM-b)', () => {
  it('shows the counters of the status and the six tabs, To link first', async () => {
    matchingApi();
    await openPage();
    expect(await screen.findByText('Unmatched products: 305', undefined, LONG)).toBeVisible();
    // CM-d: the expansions counter opens the Expansions tab
    expect(screen.getByRole('link', { name: 'Unmapped expansions: 2' })).toBeVisible();
    const tabs = within(screen.getByRole('tablist', { name: 'Matching sections' })).getAllByRole(
      'tab',
    );
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      'To link',
      'Linked',
      'Conflicts',
      'Ignored',
      'Auto-match',
      'Expansions',
    ]);
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel', { name: 'To link' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Back to Cardmarket' })).toHaveAttribute(
      'href',
      '/riftbound/app/admin/cardmarket',
    );
  });

  it('arrow keys move between the tabs and the tab goes to the URL', async () => {
    matchingApi();
    const { where } = await openPage();
    const first = await screen.findByRole('tab', { name: 'To link' }, LONG);
    first.focus();
    await userEvent.keyboard('{ArrowRight}');
    const linked = screen.getByRole('tab', { name: 'Linked' });
    expect(linked).toHaveFocus();
    await vi.waitFor(() => expect(linked).toHaveAttribute('aria-selected', 'true'));
    expect(where()).toBe(`${PATH}?tab=linked`);
    await userEvent.keyboard('{End}');
    await vi.waitFor(() =>
      expect(screen.getByRole('tab', { name: 'Expansions' })).toHaveAttribute(
        'aria-selected',
        'true',
      ),
    );
    await userEvent.keyboard('{ArrowRight}');
    await vi.waitFor(() =>
      expect(screen.getByRole('tab', { name: 'To link' })).toHaveAttribute('aria-selected', 'true'),
    );
    expect(where()).toBe(PATH);
  });

  it('switching tab drops the filters of the previous one', async () => {
    matchingApi();
    const { where } = await openPage(`${PATH}?q=ahri&type=single`);
    await userEvent.click(await screen.findByRole('tab', { name: 'Ignored' }, LONG));
    expect(where()).toBe(`${PATH}?tab=ignored`);
  });

  it('has no axe violations at 1280 and at 390, where the computer hint shows', async () => {
    matchingApi();
    const wide = await openPage();
    await screen.findByRole('list', { name: 'Products to link' }, LONG);
    expect(await axe(wide.container)).toHaveNoViolations();
    wide.unmount();

    matchingApi();
    const phone = await openPage(PATH, 390);
    await screen.findByRole('list', { name: 'Products to link' }, LONG);
    expect(screen.getByText(/easier on a computer/i)).toBeVisible();
    expect(await axe(phone.container)).toHaveNoViolations();
  });

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
