import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { exportCsv } from '@/test/fixtures/collection';
import { API, NO_PREFS, failure, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const MB2 = 2 * 1024 * 1024;

type Sent = { path: string; body: Record<string, unknown> };
const sent: Sent[] = [];

beforeEach(() => {
  clearToasts();
  sent.length = 0;
  server.use(http.get(`${API}/auth/session`, () => signedInSession(NO_PREFS)));
  server.events.on('request:start', async ({ request }) => {
    const path = new URL(request.url).pathname.replace(API, '');
    if (!path.startsWith('/collection/import')) return;
    sent.push({ path, body: (await request.clone().json()) as Record<string, unknown> });
  });
});

afterEach(() => {
  server.events.removeAllListeners();
  vi.restoreAllMocks();
});

async function openWizard(width = 1280) {
  const rendered = await renderApp({ path: '/collection/import', width });
  expect(await screen.findByRole('heading', { name: 'Import collection' }, LONG)).toBeVisible();
  return rendered;
}

const current = () =>
  within(screen.getByRole('list', { name: 'Import collection' }))
    .getAllByRole('listitem')
    .find((item) => item.getAttribute('aria-current') === 'step');

async function pasteAndReview(text = exportCsv) {
  await userEvent.click(screen.getByRole('textbox', { name: 'Or paste the content here' }));
  await userEvent.paste(text);
  await userEvent.click(screen.getByRole('button', { name: 'Review' }));
  await screen.findByText(
    'OK: 1 · With warnings: 1 · With errors: 1 · Distinct cards: 2',
    {},
    LONG,
  );
}

async function toModeStep() {
  await pasteAndReview();
  await userEvent.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByRole('group', { name: 'Mode' });
}

describe('ImportWizard step 1 (F3-i S2)', () => {
  it('has four steps, the first one current, and the RBAPP hint', async () => {
    await openWizard();
    const steps = within(screen.getByRole('list', { name: 'Import collection' })).getAllByRole(
      'listitem',
    );
    expect(steps.map((step) => step.textContent)).toEqual(['1File', '2Review', '3Mode', '4Result']);
    expect(current()).toHaveTextContent('File');
    expect(screen.getByLabelText('CSV file in RBAPP format')).toHaveAttribute('accept', '.csv');
    expect(
      screen.getByText('For now only the RBAPP format is supported (the one "Export" creates).'),
    ).toBeVisible();
  }, 15000);

  it('sends the pasted text to the preview', async () => {
    await openWizard();
    await pasteAndReview();
    expect(sent).toEqual([{ path: '/collection/import/preview', body: { text: exportCsv } }]);
    expect(current()).toHaveTextContent('Review');
  }, 20000);

  it('reads a chosen file as text and sends it', async () => {
    await openWizard();
    const file = new File([exportCsv], 'mine.csv', { type: 'text/csv' });
    await userEvent.upload(screen.getByLabelText('CSV file in RBAPP format'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Review' }));
    await screen.findByText(/OK: 1/, {}, LONG);
    expect(sent).toEqual([{ path: '/collection/import/preview', body: { text: exportCsv } }]);
  }, 20000);

  it('checks for nothing to send and for a file over 2 MB before asking the server', async () => {
    await openWizard();
    await userEvent.click(screen.getByRole('button', { name: 'Review' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Choose a file or paste the content.',
    );
    const big = new File(['x'], 'big.csv', { type: 'text/csv' });
    Object.defineProperty(big, 'size', { value: MB2 + 1 });
    await userEvent.upload(screen.getByLabelText('CSV file in RBAPP format'), big);
    await userEvent.click(screen.getByRole('button', { name: 'Review' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The file is larger than 2 MB.');
    expect(sent).toEqual([]);
    expect(current()).toHaveTextContent('File');
  }, 20000);

  it('shows import_format_unknown on the first step', async () => {
    server.use(
      http.post(`${API}/collection/import/preview`, () =>
        failure(400, { error: 'Validation Error', code: 'import_format_unknown' }),
      ),
    );
    await openWizard();
    await userEvent.click(screen.getByRole('textbox', { name: 'Or paste the content here' }));
    await userEvent.paste('name;qty\nAyla;1');
    await userEvent.click(screen.getByRole('button', { name: 'Review' }));
    expect(await screen.findByRole('alert', {}, LONG)).toHaveTextContent(
      "The file format is not recognised. Use the RBAPP format (the app's export).",
    );
    expect(current()).toHaveTextContent('File');
  }, 20000);
});

describe('ImportWizard review (F3-i S2)', () => {
  it('lists every row with its status, card and joined reasons', async () => {
    await openWizard();
    await pasteAndReview();
    expect(screen.getByText('Rows with errors will not be imported.')).toBeVisible();
    const table = screen.getByRole('table', { name: 'Review' });
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers).toEqual(expect.arrayContaining(['Line', 'Status', 'Card', 'Reasons']));
    const ayla = within(table).getByRole('row', { name: /Ayla/ });
    expect(within(ayla).getByText('OK')).toBeVisible();
    expect(within(ayla).getByText('OGN · #79')).toBeVisible();
    expect(within(ayla).getByText('0.80 €')).toBeVisible();
    const ember = within(table).getByRole('row', { name: /Ember Wisp/ });
    expect(within(ember).getByText('Warning')).toBeVisible();
    expect(
      within(ember).getByText(
        'The name does not match; the catalog name is used. Unknown condition; imported without one.',
      ),
    ).toBeVisible();
    const missing = within(table).getByRole('row', { name: /XXX · #999/ });
    expect(within(missing).getByText('Error')).toBeVisible();
    expect(within(missing).getByText('The card is not in the catalog.')).toBeVisible();
  }, 20000);

  it('filters the rows by status', async () => {
    await openWizard();
    await pasteAndReview();
    const table = screen.getByRole('table', { name: 'Review' });
    await userEvent.click(screen.getByRole('radio', { name: 'Error' }));
    expect(within(table).queryByRole('row', { name: /Ayla/ })).toBeNull();
    expect(within(table).getByRole('row', { name: /XXX · #999/ })).toBeVisible();
    await userEvent.click(screen.getByRole('radio', { name: 'Warning' }));
    expect(within(table).getByRole('row', { name: /Ember Wisp/ })).toBeVisible();
    expect(within(table).queryByRole('row', { name: /XXX/ })).toBeNull();
    await userEvent.click(screen.getByRole('radio', { name: 'All' }));
    expect(within(table).getAllByRole('row')).toHaveLength(4);
  }, 20000);

  it('goes back to the first step keeping the text', async () => {
    await openWizard();
    await pasteAndReview();
    await userEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByRole('textbox', { name: 'Or paste the content here' })).toHaveValue(
      exportCsv,
    );
    expect(current()).toHaveTextContent('File');
  }, 20000);
});

describe('ImportWizard commit (F3-i S2, S4)', () => {
  it('adds by default, shows the result and refreshes the collection queries', async () => {
    const { queryClient, where } = await openWizard();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    await toModeStep();
    expect(current()).toHaveTextContent('Mode');
    expect(screen.getByRole('radio', { name: 'Add to my collection' })).toBeChecked();
    expect(screen.getByText('Adds the copies; identical lines are merged.')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Import' }));
    expect(
      await screen.findByText('Created: 2 · Merged: 0 · Cards replaced: 0 · Skipped: 1', {}, LONG),
    ).toBeVisible();
    expect(current()).toHaveTextContent('Result');
    expect(sent[1]).toEqual({
      path: '/collection/import/commit',
      body: { preview_id: 'prev-1', mode: 'add' },
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['collection'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['cards'] });

    await userEvent.click(screen.getByRole('button', { name: 'Import another file' }));
    expect(current()).toHaveTextContent('File');
    expect(screen.getByRole('textbox', { name: 'Or paste the content here' })).toHaveValue('');

    await toModeStep();
    await userEvent.click(screen.getByRole('button', { name: 'Import' }));
    await userEvent.click(await screen.findByRole('link', { name: 'Go to the collection' }, LONG));
    await waitFor(() => expect(where()).toBe('/collection'));
  }, 30000);

  it('replace asks first, with the number of cards, and sends the mode', async () => {
    await openWizard();
    await toModeStep();
    await userEvent.click(screen.getByRole('radio', { name: 'Replace these cards' }));
    expect(
      screen.getByText(
        "For each card in the file your current lines of that card are deleted and the file's lines are added. The rest of your collection does not change.",
      ),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Import' }));
    let confirm = await screen.findByRole('dialog', { name: 'Replace these cards' });
    expect(within(confirm).getByText('Replace 2 cards in your collection?')).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(sent.filter((one) => one.path.endsWith('/commit'))).toEqual([]);

    await userEvent.click(screen.getByRole('button', { name: 'Import' }));
    confirm = await screen.findByRole('dialog', { name: 'Replace these cards' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Import' }));
    expect(
      await screen.findByText('Created: 2 · Merged: 0 · Cards replaced: 2 · Skipped: 1', {}, LONG),
    ).toBeVisible();
    expect(sent[1].body).toEqual({ preview_id: 'prev-1', mode: 'replace' });
  }, 30000);

  it('an expired preview goes back to the first step with the reason', async () => {
    server.use(
      http.post(`${API}/collection/import/commit`, () =>
        failure(410, { error: 'Gone', code: 'import_expired' }),
      ),
    );
    await openWizard();
    await toModeStep();
    await userEvent.click(screen.getByRole('button', { name: 'Import' }));
    expect(await screen.findByRole('alert', {}, LONG)).toHaveTextContent(
      'The preview expired. Upload the file again.',
    );
    expect(current()).toHaveTextContent('File');
  }, 25000);
});

describe('ImportWizard entry points and states (F3-i S2-S3)', () => {
  it('the collection toolbar links to the wizard', async () => {
    const { where } = await renderApp({ path: '/collection', width: 1280 });
    await userEvent.click(await screen.findByRole('link', { name: 'Import' }, LONG));
    await waitFor(() => expect(where()).toBe('/collection/import'));
    expect(await screen.findByRole('heading', { name: 'Import collection' }, LONG)).toBeVisible();
  }, 20000);

  it('offline: says why and disables the actions', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openWizard(390);
    expect(screen.getByText('You need a connection to make changes.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Review' })).toBeDisabled();
    expect(screen.getByLabelText('CSV file in RBAPP format')).toBeDisabled();
    expect(screen.getByRole('textbox', { name: 'Or paste the content here' })).toBeDisabled();
  }, 15000);

  it('marks the busy preview button', async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post(`${API}/collection/import/preview`, async () => {
        await gate;
        return failure(400, { code: 'import_format_unknown' });
      }),
    );
    await openWizard();
    await userEvent.click(screen.getByRole('textbox', { name: 'Or paste the content here' }));
    await userEvent.paste('x');
    await userEvent.click(screen.getByRole('button', { name: 'Review' }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Review' })).toHaveAttribute('aria-busy', 'true'),
    );
    release();
    await screen.findByRole('alert', {}, LONG);
  }, 20000);
});

describe.each([390, 1280, 1700])('ImportWizard layout at %i px (F3-i S3)', (width) => {
  it('shows the review as a list on a phone and as a table from 860 px; axe clean', async () => {
    const { container } = await openWizard(width);
    expect(await axe(container)).toHaveNoViolations();
    await pasteAndReview();
    if (width < 860) {
      expect(screen.queryByRole('table', { name: 'Review' })).toBeNull();
      const list = screen.getByRole('list', { name: 'Review' });
      expect(within(list).getAllByRole('listitem')).toHaveLength(3);
      expect(within(list).getByText('The card is not in the catalog.')).toBeVisible();
    } else {
      expect(screen.getByRole('table', { name: 'Review' })).toBeVisible();
    }
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('group', { name: 'Mode' });
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
