import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import type { AdminCard } from '@/api/endpoints';
import { clearToasts } from '@/components/ui/toastStore';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

function card(setId: string, cardId: string, name: string): AdminCard {
  return {
    set_id: setId,
    card_id: cardId,
    key: `${setId}-${cardId}`,
    name,
    domain: null,
    type: 'Rune',
    tags: null,
    energy: null,
    power: null,
    might: null,
    ability: null,
    rarity: 'Common',
    artist: null,
    image: null,
    image_url: null,
    image_src: null,
    has_image: false,
  };
}

const CATALOG = [
  card('OGN', '66', 'Fury Rune'),
  card('OGN', '67', 'Calm Rune'),
  card('PLAT', 'sfd189', 'Plated Jinx'),
  card('OGN', '166', 'Other'),
];

let append: MockInstance<FormData['append']>;
beforeEach(() => {
  append = vi.spyOn(FormData.prototype, 'append');
});
afterEach(() => {
  vi.restoreAllMocks();
  clearToasts();
});

function bulkApi({ failing = '' } = {}) {
  const uploads: string[] = [];
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/images/summary`, () =>
      ok({ cards: { missing: 4, total: 4 }, products: { missing: 0, total: 0 } }),
    ),
    http.get(`${API}/admin/sets`, () => ok([])),
    http.get(`${API}/admin/overview`, () => ok({ catalog: { sets: 1, cards: 4 } })),
    http.get(`${API}/admin/cards`, ({ request }) => {
      const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
      const items = q
        ? CATALOG.filter((one) => one.key.toLowerCase() === q || one.name.toLowerCase().includes(q))
        : CATALOG;
      return ok({ items, meta: { page: 1, per_page: 50, total: items.length, pages: 1 } });
    }),
    // jsdom's FormData cannot be read back by MSW in Node, and two uploads run at once: the
    // targets are recorded here, the file names on `FormData.append`.
    http.post(`${API}/admin/cards/:set/:id/image`, ({ params }) => {
      const key = `${String(params.set)}-${String(params.id)}`;
      uploads.push(key);
      if (key === failing) {
        return failure(400, {
          error: 'Validation Error',
          message: 'Invalid request data',
          code: 'validation_error',
          details: [
            {
              field: 'file',
              message: 'image is too small',
              type: 'value_error',
              code: 'too_small',
              params: { min: 200 },
            },
          ],
        });
      }
      const found = CATALOG.find((one) => one.key === key);
      return ok({
        ...found,
        image: `${key.toLowerCase().replace('-', '_')}.webp`,
        previous: null,
        width: 640,
        height: 894,
        bytes: 1000,
        has_image: true,
      });
    }),
  );
  return uploads;
}

const image = (name: string, type = 'image/png', size?: number) => {
  const file = new File(['bytes'], name, { type });
  if (size !== undefined) Object.defineProperty(file, 'size', { value: size });
  return file;
};

async function openBulk(files: File[]) {
  const app = await renderApp({ path: '/admin/images', width: 1280 });
  await userEvent.click(await screen.findByRole('button', { name: 'Upload several images' }, LONG));
  const dialog = await screen.findByRole('dialog', { name: 'Upload several images' });
  const input = dialog.querySelector('input[type="file"]') as HTMLInputElement;
  expect(input).toHaveAttribute('multiple');
  expect(input).toHaveAttribute('accept', 'image/png,image/jpeg,image/webp');
  // the browser's picker filters by `accept`; a drop or "All files" does not
  await userEvent.setup({ applyAccept: false }).upload(input, files);
  const table = await within(dialog).findByRole('table', { name: 'Files and where they go' });
  return { app, dialog, table };
}

const statuses = (table: HTMLElement) =>
  within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => {
      const [file, target, status] = within(row).getAllByRole('cell');
      return [
        file.textContent,
        target.textContent?.replace(/Assign by hand$/, ''),
        status.textContent,
      ];
    });

describe('BulkUploadDialog (F13-h S6, AC5)', () => {
  it('matches by file name, flags duplicates, sends nothing before the confirm', async () => {
    const uploads = bulkApi();
    const { app, dialog, table } = await openBulk([
      image('OGN-67.jpg', 'image/jpeg'),
      image('ogn_66.png'),
      image('ogn-66.jpg', 'image/jpeg'),
      image('plat_sfd189.png'),
      image('ogn_999.png'),
      image('notes.txt', 'text/plain'),
      image('huge.png', 'image/png', 10 * 1024 * 1024 + 1),
    ]);
    await waitFor(() =>
      expect(statuses(table)).toEqual([
        ['OGN-67.jpg', 'OGN-67 · Calm Rune', 'Ready'],
        ['ogn_66.png', 'OGN-66 · Fury Rune', 'Several matches'],
        ['ogn-66.jpg', 'OGN-66 · Fury Rune', 'Several matches'],
        ['plat_sfd189.png', 'PLAT-sfd189 · Plated Jinx', 'Ready'],
        ['ogn_999.png', '—', 'No match'],
        ['notes.txt', '—', 'Not an image'],
        ['huge.png', '—', 'Too large'],
      ]),
    );
    expect(uploads).toEqual([]);
    expect(within(dialog).getByRole('button', { name: 'Upload 2 images' })).toBeEnabled();
    expect(await axe(app.container)).toHaveNoViolations();
  }, 30000);

  it('an unmatched file is assigned by hand, then the batch goes on past a failure', async () => {
    const uploads = bulkApi({ failing: 'OGN-67' });
    const { dialog, table } = await openBulk([
      image('OGN-67.jpg', 'image/jpeg'),
      image('scan-001.png'),
      image('plat_sfd189.png'),
    ]);
    await waitFor(() => expect(statuses(table)[1][2]).toBe('No match'));
    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Assign scan-001.png by hand' }),
    );
    await userEvent.type(
      within(dialog).getByRole('textbox', { name: 'Search a card by name or code' }),
      'fury',
    );
    await userEvent.click(
      await within(dialog).findByRole('button', { name: 'Use OGN-66 Fury Rune' }, LONG),
    );
    await waitFor(() =>
      expect(statuses(table)[1]).toEqual(['scan-001.png', 'OGN-66 · Fury Rune', 'Ready']),
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Upload 3 images' }));
    expect(await within(dialog).findByText('2 uploaded, 1 failed.', undefined, LONG)).toBeVisible();
    expect([...uploads].sort()).toEqual(['OGN-66', 'OGN-67', 'PLAT-sfd189']);
    expect(append.mock.calls.map(([, file]) => (file as File).name).sort()).toEqual([
      'OGN-67.jpg',
      'plat_sfd189.png',
      'scan-001.png',
    ]);
    expect(statuses(table).map((row) => row[2])).toEqual([
      'FailedThe image is too small: its short side must be at least 200 px.',
      'Uploaded',
      'Uploaded',
    ]);
    expect(within(dialog).getByRole('status')).toHaveTextContent('2 uploaded, 1 failed.');
  }, 30000);

  it('keeps at most 50 files', async () => {
    bulkApi();
    const files = Array.from({ length: 51 }, (_, index) => image(`ogn_${index + 1000}.png`));
    const { dialog, table } = await openBulk(files);
    expect(
      within(dialog).getByText('At most 50 files at a time: only the first 50 were kept.'),
    ).toBeVisible();
    expect(within(table).getAllByRole('row')).toHaveLength(51);
  }, 30000);
});
