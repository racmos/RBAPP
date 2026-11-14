/** F9-i AC3 (S5, S6, S14): change the profile photo with a preview, or remove it. */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { axe } from 'vitest-axe';
import type { MeData, Session } from '@/api/types';
import { API, ME, NO_PREFS, USER, USER_TOKEN, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const NEW_URL = '/riftbound/api/v1/users/7/avatar?v=1';
const OLD_URL = '/riftbound/api/v1/users/7/avatar?v=3';
const uploads: Array<{ field: string; name: string; multipart: boolean }> = [];
let append: MockInstance<FormData['append']>;
let deletes = 0;
const createObjectURL = vi.fn(() => 'blob:preview-1');
const revokeObjectURL = vi.fn();

beforeEach(() => {
  uploads.length = 0;
  deletes = 0;
  createObjectURL.mockClear();
  revokeObjectURL.mockClear();
  // jsdom has no object URLs.
  Object.assign(URL, { createObjectURL, revokeObjectURL });
  append = vi.spyOn(FormData.prototype, 'append');
});
afterEach(() => {
  vi.restoreAllMocks();
});

type Answer = () => Response;

function signedIn({
  avatar = null,
  upload = () => ok({ avatar_url: NEW_URL }),
}: { avatar?: string | null; upload?: Answer } = {}) {
  const user = { ...USER, avatar_url: avatar };
  server.use(
    http.get(`${API}/auth/session`, () =>
      ok({ authenticated: true, csrf_token: USER_TOKEN, user, prefs: NO_PREFS }),
    ),
    http.get(`${API}/me`, () =>
      ok({ ...ME, user, profile: { ...ME.profile, avatar_url: avatar } }),
    ),
    // jsdom's FormData cannot be read back by MSW in Node: the field is recorded on append.
    http.post(`${API}/me/avatar`, ({ request }) => {
      const [field, file] = append.mock.calls.at(-1) as [string, File];
      uploads.push({
        field,
        name: file.name,
        multipart: request.headers.get('content-type')?.startsWith('multipart/form-data') ?? false,
      });
      return upload();
    }),
    http.delete(`${API}/me/avatar`, () => {
      deletes += 1;
      return ok({ avatar_url: null });
    }),
  );
}

async function openProfile() {
  const app = await renderApp({ path: '/account/profile', width: 390 });
  await screen.findByRole('form', { name: 'Details' }, LONG);
  return app;
}

const identity = () => within(screen.getByRole('region', { name: 'Identity' }));
const fileInput = () =>
  screen
    .getByRole('region', { name: 'Identity' })
    .querySelector('input[type="file"]') as HTMLInputElement;

/** A small image file; `size` fakes a bigger one (never sent: the browser refuses it). */
function image(name = 'me.png', size?: number, type = 'image/png'): File {
  const file = new File(['png-bytes'], name, { type });
  if (size !== undefined) Object.defineProperty(file, 'size', { value: size });
  return file;
}

async function choose(file: File) {
  await userEvent.click(identity().getByRole('button', { name: 'Change photo' }));
  await userEvent.upload(fileInput(), file);
}

describe('Change photo (F9-i S5)', () => {
  it('opens a file picker for the four image types', async () => {
    signedIn();
    await openProfile();
    expect(fileInput()).toHaveAttribute('accept', 'image/jpeg,image/png,image/webp,image/gif');
  }, 20000);

  it('refuses a file over 5 MB in the browser and sends nothing', async () => {
    signedIn();
    await openProfile();
    await choose(image('big.jpg', 5 * 1024 * 1024 + 1, 'image/jpeg'));
    expect(await identity().findByText('The file is too large (maximum 5 MB).')).toBeVisible();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(createObjectURL).not.toHaveBeenCalled();
    expect(uploads).toEqual([]);
  }, 20000);

  it('previews the photo cropped in a circle; "Use this photo" uploads it', async () => {
    signedIn();
    const { queryClient } = await openProfile();
    await choose(image());
    const dialog = await screen.findByRole('dialog', { name: 'New profile photo' }, LONG);
    const preview = within(dialog).getByRole('img');
    expect(preview).toHaveAttribute('src', 'blob:preview-1');
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toBeVisible();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Use this photo' }));
    expect(await screen.findByText('Profile photo updated.', {}, LONG)).toBeVisible();
    expect(uploads).toEqual([{ field: 'file', name: 'me.png', multipart: true }]);
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview-1');

    expect(queryClient.getQueryData<Session>(['session'])?.user?.avatar_url).toBe(NEW_URL);
    const me = queryClient.getQueryData<MeData>(['me']);
    expect(me?.user.avatar_url).toBe(NEW_URL);
    expect(me?.profile.avatar_url).toBe(NEW_URL);
    expect(identity().getByRole('img', { name: 'Profile photo of ada' })).toHaveAttribute(
      'src',
      `${NEW_URL}&size=256`,
    );
    expect(identity().getByRole('button', { name: 'Remove photo' })).toBeVisible();
    // the topbar shows it too
    const account = screen.getByRole('link', { name: "ada's account" });
    expect(account.querySelector('img')).toHaveAttribute('src', `${NEW_URL}&size=64`);
  }, 20000);

  it('"Cancel" closes the preview, revokes it, sends nothing and returns focus', async () => {
    signedIn();
    await openProfile();
    await choose(image());
    const dialog = await screen.findByRole('dialog', { name: 'New profile photo' }, LONG);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview-1');
    expect(uploads).toEqual([]);
    expect(identity().getByRole('button', { name: 'Change photo' })).toHaveFocus();
  }, 20000);

  it.each([
    [
      'image_invalid',
      () =>
        failure(400, {
          error: 'Validation Error',
          code: 'image_invalid',
          message: 'The file is not a supported image',
        }),
      'That file is not a supported image. Use a JPEG, PNG, WebP or GIF of at least 64 by 64 pixels.',
    ],
    [
      'file_too_large',
      () =>
        failure(413, {
          error: 'Payload Too Large',
          code: 'file_too_large',
          params: { max_mb: 5 },
        }),
      'The file is too large (maximum 5 MB).',
    ],
    [
      'rate_limited',
      () =>
        failure(429, { error: 'Too Many Requests', code: 'rate_limited' }, { 'Retry-After': '30' }),
      'Too many requests. Try again in 30 s.',
    ],
  ])(
    'a server %s keeps the preview open with the message',
    async (_code, answer, message) => {
      signedIn({ upload: answer });
      await openProfile();
      await choose(image());
      const dialog = await screen.findByRole('dialog', { name: 'New profile photo' }, LONG);
      await userEvent.click(within(dialog).getByRole('button', { name: 'Use this photo' }));
      expect(await within(dialog).findByRole('alert', {}, LONG)).toHaveTextContent(message);
      expect(screen.getByRole('dialog', { name: 'New profile photo' })).toBeVisible();
      expect(revokeObjectURL).not.toHaveBeenCalled();
    },
    20000,
  );

  it('the open preview is axe clean', async () => {
    signedIn();
    const { container } = await openProfile();
    await choose(image());
    await screen.findByRole('dialog', { name: 'New profile photo' }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});

describe('Remove photo (F9-i S6)', () => {
  it('asks first, then removes the photo and shows the initials', async () => {
    signedIn({ avatar: OLD_URL });
    const { queryClient } = await openProfile();
    await userEvent.click(identity().getByRole('button', { name: 'Remove photo' }));
    const dialog = await screen.findByRole('dialog', { name: 'Remove your profile photo?' }, LONG);
    expect(
      within(dialog).getByText('Signed-in users will see your initials instead.'),
    ).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Remove' }));
    expect(await screen.findByText('Profile photo removed.', {}, LONG)).toBeVisible();
    expect(deletes).toBe(1);
    expect(queryClient.getQueryData<Session>(['session'])?.user?.avatar_url).toBeNull();
    expect(queryClient.getQueryData<MeData>(['me'])?.profile.avatar_url).toBeNull();
    await waitFor(() =>
      expect(identity().queryByRole('button', { name: 'Remove photo' })).toBeNull(),
    );
    expect(identity().getByRole('img', { name: 'Profile photo of ada' })).toHaveTextContent('AD');
  }, 20000);

  it('cancelling keeps the photo', async () => {
    signedIn({ avatar: OLD_URL });
    await openProfile();
    await userEvent.click(identity().getByRole('button', { name: 'Remove photo' }));
    const dialog = await screen.findByRole('dialog', { name: 'Remove your profile photo?' }, LONG);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(deletes).toBe(0);
    expect(identity().getByRole('button', { name: 'Remove photo' })).toBeVisible();
  }, 20000);
});
