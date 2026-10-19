import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { API, USER, anonymousSession, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { navigateDocument } from '@/lib/navigateDocument';

vi.mock('@/lib/navigateDocument', () => ({ navigateDocument: vi.fn() }));

afterEach(() => vi.useRealTimers());

/** An API that starts anonymous and turns signed in after a good login. */
function loginFlow(respond?: () => Response | Promise<Response>) {
  let signedIn = false;
  const bodies: unknown[] = [];
  server.use(
    http.get(`${API}/auth/session`, () => (signedIn ? signedInSession() : anonymousSession())),
    http.post(`${API}/auth/login`, async ({ request }) => {
      bodies.push(await request.json());
      if (respond) return respond();
      signedIn = true;
      return ok({ user: USER });
    }),
  );
  return bodies;
}

async function fillAndSubmit(username = 'ada', password = 'correct horse', fakeTimers = false) {
  const user = userEvent.setup(fakeTimers ? { advanceTimers: vi.advanceTimersByTime } : {});
  if (username) await user.type(await screen.findByLabelText('Usuario'), username);
  if (password) await user.type(screen.getByLabelText('Contraseña'), password);
  await user.click(screen.getByRole('button', { name: 'Entrar' }));
  return user;
}

describe('LoginPage: form (FAUTH-2, FAUTH-10)', () => {
  it('has labelled fields with the right autocomplete and shows the wordmark', async () => {
    await renderApp({ path: '/login' });
    expect(await screen.findByLabelText('Usuario')).toHaveAttribute('autocomplete', 'username');
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'current-password');
    expect(screen.getByRole('img', { name: 'Rift Manager' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
  });

  it('has "Remember me" checked by default', async () => {
    await renderApp({ path: '/login' });
    expect(
      await screen.findByRole('checkbox', { name: 'Recordarme en este dispositivo' }),
    ).toBeChecked();
  });

  it('links to the register screen', async () => {
    await renderApp({ path: '/login' });
    expect(await screen.findByRole('link', { name: 'Crear cuenta' })).toHaveAttribute(
      'href',
      '/riftbound/app/register',
    );
  });

  it('is translated and sets the document title', async () => {
    await renderApp({ path: '/login', lang: 'en' });
    expect(await screen.findByLabelText('Username')).toBeVisible();
    expect(document.title).toBe('Sign in · Rift Manager');
  });
});

describe('LoginPage: success (FAUTH-2)', () => {
  it('posts remember:true by default, refetches the session and goes home', async () => {
    const bodies = loginFlow();
    const app = await renderApp({ path: '/login' });
    await fillAndSubmit();
    expect(await screen.findByText('Hola, ada')).toBeVisible();
    expect(bodies).toEqual([{ username: 'ada', password: 'correct horse', remember: true }]);
    expect(app.where()).toBe('/');
    expect(app.queryClient.getQueryData(['session'])).toMatchObject({ authenticated: true });
  });

  it('posts remember:false when the box is unchecked', async () => {
    const bodies = loginFlow();
    await renderApp({ path: '/login' });
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole('checkbox', { name: 'Recordarme en este dispositivo' }),
    );
    await user.type(screen.getByLabelText('Usuario'), 'ada');
    await user.type(screen.getByLabelText('Contraseña'), 'pw12345678');
    await user.click(screen.getByRole('button', { name: 'Entrar' }));
    await screen.findByText('Hola, ada');
    expect(bodies).toEqual([{ username: 'ada', password: 'pw12345678', remember: false }]);
  });

  it('honours next for a route inside the app', async () => {
    loginFlow();
    const app = await renderApp({
      path: '/login?next=' + encodeURIComponent('/riftbound/app/account/interface'),
    });
    await fillAndSubmit();
    await waitFor(() => expect(app.where()).toBe('/account/interface'));
  });

  it('does a full navigation for a legacy next', async () => {
    loginFlow();
    await renderApp({ path: '/login?next=' + encodeURIComponent('/riftbound/collection') });
    await fillAndSubmit();
    await waitFor(() => expect(navigateDocument).toHaveBeenCalledWith('/riftbound/collection'));
  });

  it('goes home for an unsafe next', async () => {
    loginFlow();
    const app = await renderApp({ path: '/login?next=' + encodeURIComponent('//evil.example') });
    await fillAndSubmit();
    await screen.findByText('Hola, ada');
    expect(app.where()).toBe('/');
    expect(navigateDocument).not.toHaveBeenCalled();
  });

  it('disables the submit control while the request is pending', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    loginFlow(async () => {
      await gate;
      return ok({ user: USER });
    });
    await renderApp({ path: '/login' });
    await fillAndSubmit();
    const button = await screen.findByRole('button', { name: 'Entrando…' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    release();
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Entrando…' })).not.toBeInTheDocument(),
    );
  });
});

describe('LoginPage: failures (FAUTH-2, FAUTH-10)', () => {
  const invalid = () =>
    failure(401, {
      error: 'Unauthorized',
      message: 'Invalid credentials',
      code: 'invalid_credentials',
    });

  it('shows a translated generic error, keeps the username, clears the password and focuses it', async () => {
    loginFlow(invalid);
    const app = await renderApp({ path: '/login' });
    await fillAndSubmit('ada', 'wrong password');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Usuario o contraseña incorrectos.');
    expect(alert).not.toHaveTextContent('Invalid credentials');
    expect(screen.getByLabelText('Usuario')).toHaveValue('ada');
    expect(screen.getByLabelText('Contraseña')).toHaveValue('');
    expect(screen.getByLabelText('Contraseña')).toHaveFocus();
    expect(app.where()).toBe('/login');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled();
  });

  it('translates the error to English with the language', async () => {
    loginFlow(invalid);
    await renderApp({ path: '/login', lang: 'en' });
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Username'), 'ada');
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong username or password.');
  });

  it('does not tell a missing user from a wrong password (same message for any 401)', async () => {
    loginFlow(invalid);
    await renderApp({ path: '/login' });
    await fillAndSubmit('nobody', 'whatever');
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos.');
  });

  it('maps 400 details to field errors and focuses the first invalid field', async () => {
    loginFlow(() =>
      failure(400, {
        error: 'Validation Error',
        message: 'Invalid request data',
        code: 'validation_error',
        details: [
          {
            field: 'username',
            message: 'too long',
            type: 'string_too_long',
            code: 'too_long',
            params: { max: 32 },
          },
          {
            field: 'password',
            message: 'too short',
            type: 'string_too_short',
            code: 'too_short',
            params: { min: 1 },
          },
        ],
      }),
    );
    await renderApp({ path: '/login' });
    await fillAndSubmit('ada', 'pw');
    const username = await screen.findByLabelText('Usuario');
    await waitFor(() => expect(username).toHaveFocus());
    expect(username).toHaveAttribute('aria-invalid', 'true');
    expect(username).toHaveAccessibleDescription(
      'El usuario debe tener como máximo 32 caracteres.',
    );
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('aria-invalid', 'true');
  });

  it('asks for missing fields without sending a request, focusing the first empty one', async () => {
    const bodies = loginFlow();
    await renderApp({ path: '/login' });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Entrar' }));
    expect(screen.getByLabelText('Usuario')).toHaveFocus();
    expect(screen.getByLabelText('Usuario')).toHaveAccessibleDescription(
      'Este campo es obligatorio.',
    );
    expect(screen.getByLabelText('Contraseña')).toHaveAccessibleDescription(
      'Este campo es obligatorio.',
    );
    expect(bodies).toEqual([]);
  });

  it('clears a field error once the user edits that field', async () => {
    loginFlow();
    await renderApp({ path: '/login' });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Entrar' }));
    await user.type(screen.getByLabelText('Usuario'), 'a');
    expect(screen.getByLabelText('Usuario')).not.toHaveAttribute('aria-invalid');
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows the network error and keeps what was typed', async () => {
    server.use(
      http.get(`${API}/auth/session`, () => anonymousSession()),
      http.post(`${API}/auth/login`, () => Response.error()),
    );
    await renderApp({ path: '/login' });
    await fillAndSubmit('ada', 'pw12345678');
    expect(await screen.findByRole('alert')).toHaveTextContent('No hay conexión con el servidor');
    expect(screen.getByLabelText('Usuario')).toHaveValue('ada');
  });
});

describe('LoginPage: 429 countdown (FAUTH-7)', () => {
  const limited =
    (seconds = 30) =>
    () =>
      failure(
        429,
        {
          error: 'Too Many Requests',
          message: 'locked',
          code: 'locked',
          params: { retry_after: seconds },
        },
        { 'Retry-After': String(seconds) },
      );

  it('starts a countdown near 30 s, disables submit, announces at start and at 0 only', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    loginFlow(limited());
    await renderApp({ path: '/login' });
    await fillAndSubmit('ada', 'correct horse', true);

    const countdown = await screen.findByText(/Podrás volver a intentarlo en \d+ segundos/, {
      selector: 'p',
    });
    const initial = Number(/en (\d+) segundos/.exec(countdown.textContent ?? '')![1]);
    expect(initial).toBeGreaterThanOrEqual(29);
    expect(initial).toBeLessThanOrEqual(30);
    const button = screen.getByRole('button', { name: 'Entrar' });
    expect(button).toBeDisabled();

    const live = screen.getAllByRole('status').find((el) => el.className.includes('sr-only'))!;
    const announced = live.textContent;
    expect(announced).toMatch(/Podrás volver a intentarlo en \d+ segundos/);

    await vi.advanceTimersByTimeAsync(12_000);
    expect(live.textContent).toBe(announced); // not every second
    expect(Number(/en (\d+) segundos/.exec(countdown.textContent ?? '')![1])).toBeLessThan(initial);
    expect(button).toBeDisabled();

    await vi.advanceTimersByTimeAsync(19_000);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Entrar' })).toBeEnabled());
    expect(live).toHaveTextContent('Ya puedes volver a intentarlo.');
    expect(
      screen.queryByText(/Podrás volver a intentarlo en/, { selector: 'p' }),
    ).not.toBeInTheDocument();
  });

  it('uses params.retry_after when the header is missing', async () => {
    loginFlow(() =>
      failure(429, {
        error: 'Too Many Requests',
        message: 'x',
        code: 'rate_limited',
        params: { retry_after: 7 },
      }),
    );
    await renderApp({ path: '/login' });
    await fillAndSubmit();
    expect(
      await screen.findByText(/Podrás volver a intentarlo en [67] segundos/, { selector: 'p' }),
    ).toBeVisible();
  });
});

describe('LoginPage: accessibility (FAUTH-10)', () => {
  it('has no axe violations', async () => {
    const { container } = await renderApp({ path: '/login' });
    await screen.findByLabelText('Usuario');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no axe violations in the error state', async () => {
    loginFlow(() => failure(401, { code: 'invalid_credentials', error: 'Unauthorized' }));
    const { container } = await renderApp({ path: '/login' });
    await fillAndSubmit('ada', 'wrong');
    await screen.findByRole('alert');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no axe violations with field errors', async () => {
    const { container } = await renderApp({ path: '/login' });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Entrar' }));
    expect(await axe(container)).toHaveNoViolations();
  });
});
