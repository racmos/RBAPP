import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { exportCsv } from '@/test/fixtures/collection';
import { API, NO_PREFS, failure, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

const exports: string[] = [];
const downloads: { name: string; href: string }[] = [];
const blobs: Blob[] = [];

beforeAll(() => {
  // jsdom has no object URLs; the stubs stay for the whole file (a revoke may run late).
  URL.createObjectURL = vi.fn((blob: Blob) => {
    blobs.push(blob);
    return `blob:rbapp/${blobs.length}`;
  });
  URL.revokeObjectURL = vi.fn();
});

beforeEach(() => {
  clearToasts();
  exports.length = 0;
  downloads.length = 0;
  blobs.length = 0;
  server.use(http.get(`${API}/auth/session`, () => signedInSession(NO_PREFS)));
  server.events.on('request:start', ({ request }) => {
    const url = new URL(request.url);
    if (url.pathname === `${API}/collection/export`) exports.push(url.search.slice(1));
  });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    downloads.push({ name: this.download, href: this.href });
  });
});

afterEach(() => {
  server.events.removeAllListeners();
  vi.restoreAllMocks();
  // React Query keeps the browser state it last heard of: tell it the network is back.
  window.dispatchEvent(new Event('online'));
});

async function openDialog(path = '/collection', width = 1280) {
  const rendered = await renderApp({ path, width });
  await screen.findByRole('button', { name: /Ayla/ }, LONG);
  await userEvent.click(screen.getByRole('button', { name: 'Export' }));
  const dialog = await screen.findByRole('dialog', { name: 'Export collection' });
  return { ...rendered, dialog };
}

const radio = (dialog: HTMLElement, name: string | RegExp) =>
  within(dialog).getByRole('radio', { name });

describe('ExportDialog (F3-i S1)', () => {
  it('starts on RBAPP and the whole collection; Cardmarket forces what is on sale', async () => {
    const { dialog } = await openDialog();
    expect(within(dialog).getByRole('group', { name: 'Format' })).toBeVisible();
    expect(within(dialog).getByRole('group', { name: 'What to export' })).toBeVisible();
    expect(radio(dialog, /^RBAPP/)).toBeChecked();
    expect(radio(dialog, 'The whole collection')).toBeChecked();
    expect(
      within(dialog).queryByText('The same file as the classic export, to upload to Cardmarket.'),
    ).toBeNull();

    await userEvent.click(radio(dialog, 'Cardmarket (cards on sale)'));
    expect(
      within(dialog).getByText('The same file as the classic export, to upload to Cardmarket.'),
    ).toBeVisible();
    expect(radio(dialog, 'Only what is on sale')).toBeChecked();
    expect(radio(dialog, 'The whole collection')).toBeDisabled();
    expect(radio(dialog, 'Only the current filters')).toBeDisabled();

    await userEvent.click(radio(dialog, /^RBAPP/));
    expect(radio(dialog, 'The whole collection')).toBeEnabled();
    expect(radio(dialog, 'Only the current filters')).toBeEnabled();
  }, 20000);

  it('downloads the file with the name the server gave and says how many rows', async () => {
    const { dialog } = await openDialog();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Download' }));
    await waitFor(() => expect(downloads).toHaveLength(1), LONG);
    expect(exports).toEqual(['format=rbapp']);
    expect(downloads[0].name).toBe('rbapp_collection_20261028101500.csv');
    expect(downloads[0].href).toBe('blob:rbapp/1');
    expect(await blobs[0].text()).toBe(exportCsv);
    expect(await screen.findByText('1 row exported.', {}, LONG)).toBeVisible();
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Export collection' })).toBeNull(),
    );
    // the anchor did not stay in the page
    expect(document.querySelector('a[download]')).toBeNull();
  }, 20000);

  it('sends the current URL filters, without sort or paging', async () => {
    const { dialog } = await openDialog('/collection?q=ayla&foil=nonfoil&sort=value&page=1');
    await userEvent.click(radio(dialog, 'Only the current filters'));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Download' }));
    await waitFor(() => expect(exports).toEqual(['q=ayla&foil=nonfoil&format=rbapp']), LONG);
  }, 20000);

  it('asks for the lines on sale, and Cardmarket names its own file', async () => {
    let { dialog } = await openDialog();
    await userEvent.click(radio(dialog, 'Only what is on sale'));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Download' }));
    await waitFor(() => expect(exports).toEqual(['format=rbapp&only_selling=true']), LONG);

    await userEvent.click(await screen.findByRole('button', { name: 'Export' }, LONG));
    dialog = await screen.findByRole('dialog', { name: 'Export collection' });
    await userEvent.click(radio(dialog, 'Cardmarket (cards on sale)'));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Download' }));
    await waitFor(() => expect(downloads).toHaveLength(2), LONG);
    expect(exports[1]).toBe('format=cardmarket&only_selling=true');
    expect(downloads[1].name).toBe('20261028101500_cardmarket.csv');
  }, 25000);

  it('a failure is a translated toast and the dialog stays open', async () => {
    server.use(
      http.get(`${API}/collection/export`, () =>
        failure(400, { error: 'Validation Error', code: 'validation_error' }),
      ),
    );
    const { dialog } = await openDialog();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Download' }));
    expect(await screen.findByText('Check the form data.', {}, LONG)).toBeVisible();
    expect(downloads).toHaveLength(0);
    expect(screen.getByRole('dialog', { name: 'Export collection' })).toBeVisible();
  }, 20000);

  it('offline: the download is disabled', async () => {
    const { dialog } = await openDialog();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    window.dispatchEvent(new Event('offline'));
    await waitFor(() =>
      expect(within(dialog).getByRole('button', { name: 'Download' })).toBeDisabled(),
    );
  }, 20000);

  it.each([390, 1280])(
    'offline at %i px: the toolbar button is disabled',
    async (width) => {
      vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
      await renderApp({ path: '/collection', width });
      expect(await screen.findByRole('button', { name: 'Export' }, LONG)).toBeDisabled();
    },
    20000,
  );

  it.each([390, 1280])(
    'is opened from the toolbar at %i px and is axe clean',
    async (width) => {
      const { dialog, container } = await openDialog('/collection', width);
      expect(dialog).toBeVisible();
      expect(await axe(container)).toHaveNoViolations();
    },
    25000,
  );
});
