import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { API, anonymousSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { installAltchaStub, setAltchaState } from '@/test/altchaStub';
import { renderApp } from '@/test/renderApp';

// The real library registers a Svelte custom element backed by workers; tests use a stub.
vi.mock('altcha', () => ({}));
beforeAll(installAltchaStub);

const CHALLENGE = {
  algorithm: 'SHA-256',
  challenge: 'abc',
  maxnumber: 1000,
  salt: 's',
  signature: 'sig',
};
const VALID = { username: 'new_user', email: 'new@example.com', password: 'longenough1' };

/** Server state for one register test: captcha provider, requests seen and the register answer. */
function registerApi({
  provider = 'none',
  challenge = null as Record<string, unknown> | null,
  answer = () => ok({ user: { id: 9, username: 'new_user' } }, 201) as Response | Promise<Response>,
} = {}) {
  const state = { captchaGets: 0, bodies: [] as Record<string, unknown>[] };
  server.use(
    http.get(`${API}/auth/session`, () => anonymousSession()),
    http.get(`${API}/meta/config`, () =>
      ok({
        env: 'test',
        registration_open: true,
        captcha: { provider, required_for: provider === 'none' ? [] : ['register'] },
        csrf: { header: 'X-CSRFToken' },
      }),
    ),
    http.get(`${API}/auth/captcha`, () => {
      state.captchaGets += 1;
      return ok({
        provider,
        challenge: challenge && { ...challenge, salt: `salt-${state.captchaGets}` },
      });
    }),
    http.post(`${API}/auth/register`, async ({ request }) => {
      state.bodies.push((await request.json()) as Record<string, unknown>);
      return answer();
    }),
  );
  return state;
}

async function fill(values: Partial<typeof VALID> = VALID) {
  const user = userEvent.setup();
  const type = async (label: string, value?: string) => {
    if (value) await user.type(await screen.findByLabelText(label), value);
  };
  await type('Usuario', values.username);
  await type('Correo electrónico', values.email);
  await type('Contraseña', values.password);
  return user;
}

const widget = (container: HTMLElement) => container.querySelector('altcha-widget');
const submit = () => screen.getByRole('button', { name: /Crear cuenta|Creando cuenta…/ });

describe('RegisterPage: form (FAUTH-3, FAUTH-10)', () => {
  it('labels every control with the right autocomplete and shows the wordmark', async () => {
    registerApi();
    await renderApp({ path: '/register' });
    expect(await screen.findByLabelText('Usuario')).toHaveAttribute('autocomplete', 'username');
    expect(screen.getByLabelText('Correo electrónico')).toHaveAttribute('autocomplete', 'email');
    expect(screen.getByLabelText('Correo electrónico')).toHaveAttribute('type', 'email');
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'new-password');
    expect(screen.getByRole('img', { name: 'Rift Manager' })).toBeVisible();
    expect(document.title).toBe('Crear cuenta · Rift Manager');
  });

  it('describes the username and password rules as hints', async () => {
    registerApi();
    await renderApp({ path: '/register' });
    expect(await screen.findByLabelText('Usuario')).toHaveAccessibleDescription(
      /3 a 32 caracteres/,
    );
    expect(screen.getByLabelText('Contraseña')).toHaveAccessibleDescription(
      /Entre 8 y 128 caracteres/,
    );
  });

  it('shows a loading state while the configuration loads', async () => {
    registerApi();
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.use(
      http.get(`${API}/meta/config`, async () => {
        await gate;
        return ok({
          env: 't',
          registration_open: true,
          captcha: { provider: 'none', required_for: [] },
          csrf: { header: 'X-CSRFToken' },
        });
      }),
    );
    await renderApp({ path: '/register' });
    expect(await screen.findByText('Preparando la verificación…')).toBeInTheDocument();
    expect(screen.queryByLabelText('Usuario')).not.toBeInTheDocument();
    release();
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
  });

  it('links back to login', async () => {
    registerApi();
    await renderApp({ path: '/register' });
    expect(await screen.findByRole('link', { name: 'Iniciar sesión' })).toHaveAttribute(
      'href',
      '/riftbound/app/login',
    );
  });
});

describe('RegisterPage: captcha provider (FAUTH-3)', () => {
  it('renders no widget and sends no altcha for provider none', async () => {
    const api = registerApi({ provider: 'none' });
    const { container } = await renderApp({ path: '/register' });
    const user = await fill();
    expect(widget(container)).toBeNull();
    expect(submit()).toBeEnabled();
    await user.click(submit());
    await waitFor(() => expect(api.bodies).toHaveLength(1));
    expect(api.bodies[0]).toEqual(VALID);
    expect('altcha' in api.bodies[0]).toBe(false);
  });

  it('renders no widget when the challenge is null even if a provider is named', async () => {
    const api = registerApi({ provider: 'altcha', challenge: null });
    const { container } = await renderApp({ path: '/register' });
    const user = await fill();
    expect(widget(container)).toBeNull();
    await user.click(submit());
    await waitFor(() => expect(api.bodies).toHaveLength(1));
    expect('altcha' in api.bodies[0]).toBe(false);
  });

  it('keeps submit disabled until the widget reports verified, then sends the payload', async () => {
    const api = registerApi({ provider: 'altcha', challenge: CHALLENGE });
    const { container } = await renderApp({ path: '/register' });
    const user = await fill();
    const element = widget(container)!;
    expect(element).not.toBeNull();
    expect(JSON.parse(element.getAttribute('challengejson')!)).toMatchObject({
      challenge: 'abc',
      salt: 'salt-1',
    });
    expect(element).toHaveAttribute('auto', 'onload');
    expect(submit()).toBeDisabled();
    expect(screen.getByText('Completa la verificación para continuar.')).toBeVisible();

    act(() => setAltchaState(element, 'verifying'));
    expect(submit()).toBeDisabled();
    act(() => setAltchaState(element, 'verified', 'payload-1'));
    expect(submit()).toBeEnabled();
    expect(screen.queryByText('Completa la verificación para continuar.')).not.toBeInTheDocument();

    await user.click(submit());
    await waitFor(() => expect(api.bodies).toHaveLength(1));
    expect(api.bodies[0]).toEqual({ ...VALID, altcha: 'payload-1' });
  });

  it('disables submit again when the widget leaves the verified state', async () => {
    registerApi({ provider: 'altcha', challenge: CHALLENGE });
    const { container } = await renderApp({ path: '/register' });
    await screen.findByLabelText('Usuario');
    const element = widget(container)!;
    act(() => setAltchaState(element, 'verified', 'p'));
    expect(submit()).toBeEnabled();
    act(() => setAltchaState(element, 'error'));
    expect(submit()).toBeDisabled();
  });

  it('fetches a fresh challenge when the verification expires', async () => {
    const api = registerApi({ provider: 'altcha', challenge: CHALLENGE });
    const { container } = await renderApp({ path: '/register' });
    await screen.findByLabelText('Usuario');
    const first = widget(container)!;
    act(() => setAltchaState(first, 'verified', 'p'));
    act(() => setAltchaState(first, 'expired'));
    await waitFor(() => expect(api.captchaGets).toBe(2));
    await waitFor(() => expect(widget(container)).not.toBe(first));
    expect(JSON.parse(widget(container)!.getAttribute('challengejson')!).salt).toBe('salt-2');
    expect(submit()).toBeDisabled();
  });

  it('groups the widget under a labelled security check', async () => {
    registerApi({ provider: 'altcha', challenge: CHALLENGE });
    await renderApp({ path: '/register' });
    expect(await screen.findByRole('group', { name: 'Verificación de seguridad' })).toBeVisible();
  });
});

describe('RegisterPage: outcomes (FAUTH-3)', () => {
  it('goes to /login with a success toast and keeps the session anonymous after a 201', async () => {
    registerApi();
    const app = await renderApp({ path: '/register' });
    const user = await fill();
    await user.click(submit());
    expect(await screen.findByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    expect(app.where()).toBe('/login');
    expect(await screen.findByRole('region', { name: 'Notificaciones' })).toHaveTextContent(
      'Cuenta creada. Ya puedes iniciar sesión.',
    );
    expect(app.queryClient.getQueryData(['session'])).toMatchObject({ authenticated: false });
    expect(screen.getByLabelText('Usuario')).toHaveValue('new_user');
  });

  it.each([
    ['username_taken', 'Usuario', 'Ese nombre de usuario ya está en uso.'],
    ['email_taken', 'Correo electrónico', 'Ese correo electrónico ya está registrado.'],
  ])('shows %s on its field, focuses it and announces it', async (code, label, text) => {
    registerApi({
      answer: () => failure(409, { error: 'Conflict', message: 'English prose', code }),
    });
    await renderApp({ path: '/register' });
    const user = await fill();
    await user.click(submit());
    const field = await screen.findByLabelText(label);
    await waitFor(() => expect(field).toHaveFocus());
    expect(field).toHaveAccessibleDescription(expect.stringContaining(text));
    expect(field).toHaveAttribute('aria-invalid', 'true');
    const live = screen.getAllByRole('status').find((el) => el.className.includes('sr-only'))!;
    expect(live).toHaveTextContent(text);
  });

  it('shows a captcha failure as a form error', async () => {
    registerApi({
      answer: () =>
        failure(400, {
          error: 'Captcha Error',
          message: 'Captcha verification failed',
          code: 'captcha_failed',
        }),
    });
    await renderApp({ path: '/register' });
    const user = await fill();
    await user.click(submit());
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La verificación de seguridad ha fallado',
    );
  });

  it('maps 400 details onto the matching fields', async () => {
    registerApi({
      answer: () =>
        failure(400, {
          error: 'Validation Error',
          code: 'validation_error',
          details: [
            { field: 'email', message: 'bad', type: 'invalid_format', code: 'invalid_format' },
            {
              field: 'password',
              message: 'short',
              type: 'string_too_short',
              code: 'too_short',
              params: { min: 8 },
            },
          ],
        }),
    });
    await renderApp({ path: '/register' });
    const user = await fill();
    await user.click(submit());
    const email = await screen.findByLabelText('Correo electrónico');
    await waitFor(() => expect(email).toHaveFocus());
    expect(email).toHaveAccessibleDescription('Introduce un correo electrónico válido.');
    expect(screen.getByLabelText('Contraseña')).toHaveAccessibleDescription(
      expect.stringContaining('al menos 8 caracteres'),
    );
  });
});

describe('RegisterPage: the captcha payload is single use (FAUTH-4)', () => {
  const errors: [string, () => Response | Promise<Response>][] = [
    ['400', () => failure(400, { error: 'Validation Error', code: 'validation_error' })],
    ['409', () => failure(409, { error: 'Conflict', code: 'username_taken' })],
    [
      '429',
      () =>
        failure(
          429,
          { error: 'Too Many Requests', code: 'rate_limited', params: { retry_after: 20 } },
          { 'Retry-After': '20' },
        ),
    ],
    ['500', () => failure(500, { error: 'Internal Server Error' })],
    ['network', () => Response.error()],
  ];

  it.each(errors)(
    'after a %s error: new captcha request, widget remounted, submit disabled until re-verified',
    async (_label, answer) => {
      const api = registerApi({ provider: 'altcha', challenge: CHALLENGE, answer });
      const { container } = await renderApp({ path: '/register' });
      const user = await fill();
      const first = widget(container)!;
      act(() => setAltchaState(first, 'verified', 'burned'));
      await user.click(submit());

      await waitFor(() => expect(api.captchaGets).toBe(2));
      await waitFor(() => expect(widget(container)).not.toBe(first));
      const second = widget(container)!;
      expect(JSON.parse(second.getAttribute('challengejson')!).salt).toBe('salt-2');
      expect(submit()).toBeDisabled();
    },
  );

  it('enables submit again once the new widget is verified', async () => {
    const api = registerApi({
      provider: 'altcha',
      challenge: CHALLENGE,
      answer: () => failure(409, { error: 'Conflict', code: 'email_taken' }),
    });
    const { container } = await renderApp({ path: '/register' });
    const user = await fill();
    act(() => setAltchaState(widget(container)!, 'verified', 'burned'));
    await user.click(submit());
    await waitFor(() => expect(api.captchaGets).toBe(2));
    await waitFor(() => expect(submit()).toBeDisabled());
    act(() => setAltchaState(widget(container)!, 'verified', 'fresh'));
    expect(submit()).toBeEnabled();
  });

  it('sends the fresh payload on the next attempt and never the burned one', async () => {
    let attempt = 0;
    const api = registerApi({
      provider: 'altcha',
      challenge: CHALLENGE,
      answer: () =>
        ++attempt === 1
          ? failure(409, { error: 'Conflict', code: 'username_taken' })
          : ok({ user: { id: 1, username: 'x' } }, 201),
    });
    const { container } = await renderApp({ path: '/register' });
    const user = await fill();
    act(() => setAltchaState(widget(container)!, 'verified', 'burned'));
    await user.click(submit());
    await waitFor(() => expect(api.captchaGets).toBe(2));
    await waitFor(() => expect(submit()).toBeDisabled());
    const next = widget(container)!;
    act(() => setAltchaState(next, 'verified', 'fresh'));
    await user.clear(screen.getByLabelText('Usuario'));
    await user.type(screen.getByLabelText('Usuario'), 'other_name');
    await user.click(submit());
    await waitFor(() => expect(api.bodies).toHaveLength(2));
    expect(api.bodies.map((body) => body.altcha)).toEqual(['burned', 'fresh']);
  });

  it('refetches the captcha after an error even when no widget was in use', async () => {
    const api = registerApi({
      provider: 'none',
      answer: () => failure(500, { error: 'Internal Server Error' }),
    });
    await renderApp({ path: '/register' });
    const user = await fill();
    await user.click(submit());
    await waitFor(() => expect(api.captchaGets).toBe(2));
  });
});

describe('RegisterPage: client checks (FAUTH-10)', () => {
  it.each([
    ['username', { ...VALID, username: 'ab' }, 'Usuario', /Usa de 3 a 32 caracteres/],
    [
      'username with a space',
      { ...VALID, username: 'bad name' },
      'Usuario',
      /Usa de 3 a 32 caracteres/,
    ],
    [
      'username with a symbol',
      { ...VALID, username: 'bad!' },
      'Usuario',
      /Usa de 3 a 32 caracteres/,
    ],
    [
      'email',
      { ...VALID, email: 'not-an-email' },
      'Correo electrónico',
      /correo electrónico válido/,
    ],
    ['short password', { ...VALID, password: '1234567' }, 'Contraseña', /al menos 8 caracteres/],
    [
      'long password',
      { ...VALID, password: 'x'.repeat(129) },
      'Contraseña',
      /como máximo 128 caracteres/,
    ],
  ])(
    'rejects an invalid %s without a request and focuses it',
    async (_label, values, label, message) => {
      const api = registerApi();
      await renderApp({ path: '/register' });
      const user = await fill(values);
      await user.click(submit());
      const field = screen.getByLabelText(label);
      expect(field).toHaveFocus();
      expect(field).toHaveAttribute('aria-invalid', 'true');
      expect(field).toHaveAccessibleDescription(message);
      expect(api.bodies).toEqual([]);
      expect(api.captchaGets).toBe(1);
    },
  );

  it('asks for every missing field and focuses the first', async () => {
    const api = registerApi();
    await renderApp({ path: '/register' });
    await screen.findByLabelText('Usuario');
    await userEvent.click(submit());
    expect(screen.getByLabelText('Usuario')).toHaveFocus();
    for (const label of ['Usuario', 'Correo electrónico', 'Contraseña']) {
      expect(screen.getByLabelText(label)).toHaveAccessibleDescription(
        expect.stringContaining('obligatorio'),
      );
    }
    expect(api.bodies).toEqual([]);
  });

  it('accepts the boundary values (3 and 32 characters, 8 and 128 characters)', async () => {
    const api = registerApi();
    await renderApp({ path: '/register' });
    const user = await fill({ username: 'abc', email: 'a@b.co', password: 'x'.repeat(128) });
    await user.click(submit());
    await waitFor(() => expect(api.bodies).toHaveLength(1));
    expect(api.bodies[0].username).toBe('abc');
  });
});

describe('RegisterPage: setup failure and 429', () => {
  it('shows an error with retry when the configuration cannot be loaded', async () => {
    let failing = true;
    server.use(
      http.get(`${API}/meta/config`, () =>
        failing
          ? failure(503, { error: 'Service Unavailable', message: '' })
          : ok({
              env: 't',
              registration_open: true,
              captcha: { provider: 'none', required_for: [] },
              csrf: { header: 'X-CSRFToken' },
            }),
      ),
    );
    await renderApp({ path: '/register' });
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'El servicio no está disponible temporalmente.',
    );
    failing = false;
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
  });

  it('keeps submit disabled during a 429 countdown', async () => {
    registerApi({
      answer: () =>
        failure(
          429,
          { error: 'Too Many Requests', code: 'rate_limited', params: { retry_after: 30 } },
          { 'Retry-After': '30' },
        ),
    });
    await renderApp({ path: '/register' });
    const user = await fill();
    await user.click(submit());
    expect(
      await screen.findByText(/Podrás volver a intentarlo en \d+ segundos/, { selector: 'p' }),
    ).toBeVisible();
    expect(submit()).toBeDisabled();
  });
});

describe('RegisterPage: accessibility (FAUTH-10)', () => {
  it('has no axe violations, with a widget present', async () => {
    registerApi({ provider: 'altcha', challenge: CHALLENGE });
    const { container } = await renderApp({ path: '/register' });
    await screen.findByLabelText('Usuario');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('has no axe violations in the error state', async () => {
    registerApi();
    const { container } = await renderApp({ path: '/register' });
    await screen.findByLabelText('Usuario');
    await userEvent.click(submit());
    expect(screen.getByLabelText('Usuario')).toHaveAttribute('aria-invalid', 'true');
    expect(await axe(container)).toHaveNoViolations();
  });
});
