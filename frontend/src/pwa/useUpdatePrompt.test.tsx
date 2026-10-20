import { act, fireEvent, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LiveAnnouncer } from '@/components/ui/LiveAnnouncer';
import { clearToasts } from '@/components/ui/toastStore';
import { ToastStack } from '@/components/ui/Toast';
import { renderWithI18n } from '@/test/i18n';
import { UPDATE_CHECK_INTERVAL_MS } from './useUpdatePrompt';
import { UpdateToast } from './UpdateToast';

// The module the build plugin generates; here a controllable stand-in (vitest alias to a stub).
const sw = vi.hoisted(() => ({
  needRefresh: false,
  updateServiceWorker: vi.fn(),
  registerCalls: 0,
  onRegisteredSW: undefined as ((url: string, registration?: unknown) => void) | undefined,
}));
vi.mock('virtual:pwa-register/react', () => ({
  useRegisterSW: (options: { onRegisteredSW?: (url: string, registration?: unknown) => void }) => {
    sw.registerCalls += 1;
    sw.onRegisteredSW = options.onRegisteredSW;
    return {
      needRefresh: [sw.needRefresh, vi.fn()],
      offlineReady: [false, vi.fn()],
      updateServiceWorker: sw.updateServiceWorker,
    };
  },
}));

const registration = { update: vi.fn(() => Promise.resolve()) };

function Page() {
  return (
    <>
      <form>
        <label>
          Nombre del mazo
          <input defaultValue="" />
        </label>
      </form>
      <LiveAnnouncer />
      <UpdateToast />
      <ToastStack />
    </>
  );
}

async function renderPage(needRefresh = false) {
  sw.needRefresh = needRefresh;
  const view = await renderWithI18n(<Page />);
  act(() => sw.onRegisteredSW?.('/riftbound/app/sw.js', registration));
  return view;
}

const setVisibility = (state: 'visible' | 'hidden') => {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true });
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'));
  });
};

beforeEach(() => {
  sw.registerCalls = 0;
  sw.updateServiceWorker.mockClear();
  registration.update.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  setVisibility('visible');
  act(() => clearToasts());
});

describe('update toast (PWA-4)', () => {
  it('shows nothing while no new version waits', async () => {
    await renderPage(false);
    expect(screen.queryByText(/Nueva versión/, { selector: 'p' })).not.toBeInTheDocument();
  });

  it('offers the update with an "Actualizar" action and does not reload by itself', async () => {
    await renderPage(true);
    expect(screen.getByText(/Nueva versión/, { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar' })).toBeInTheDocument();
    expect(sw.updateServiceWorker).not.toHaveBeenCalled();
  });

  it('says it in English too', async () => {
    sw.needRefresh = true;
    await renderWithI18n(<Page />, 'en');
    expect(screen.getByText(/New version/, { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Update' })).toBeInTheDocument();
  });

  it('activates the waiting worker once when the action is used', async () => {
    await renderPage(true);
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    expect(sw.updateServiceWorker).toHaveBeenCalledTimes(1);
    expect(sw.updateServiceWorker).toHaveBeenCalledWith(true);
    expect(screen.queryByText(/Nueva versión/, { selector: 'p' })).not.toBeInTheDocument();
  });

  it('keeps a half-filled form when the toast is dismissed, and does not reload', async () => {
    await renderPage(true);
    const field = screen.getByLabelText('Nombre del mazo');
    fireEvent.change(field, { target: { value: 'Control de Ahri' } });

    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }));

    expect(screen.queryByText(/Nueva versión/, { selector: 'p' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Nombre del mazo')).toHaveValue('Control de Ahri');
    expect(sw.updateServiceWorker).not.toHaveBeenCalled();
  });

  it('stays until it is answered (no auto-dismiss timer)', async () => {
    vi.useFakeTimers();
    await renderPage(true);
    act(() => vi.advanceTimersByTime(30_000));
    expect(screen.getByText(/Nueva versión/, { selector: 'p' })).toBeInTheDocument();
  });

  it('is announced in the live region', async () => {
    await renderPage(true);
    expect(screen.getByRole('status')).toHaveTextContent(/Nueva versión/);
  });

  it('offers the update again at the next check when it was dismissed', async () => {
    vi.useFakeTimers();
    await renderPage(true);
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    expect(screen.queryByText(/Nueva versión/, { selector: 'p' })).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(UPDATE_CHECK_INTERVAL_MS);
    });
    expect(screen.getByText(/Nueva versión/, { selector: 'p' })).toBeInTheDocument();
  });

  it('does not stack a second toast while the first one is still showing', async () => {
    vi.useFakeTimers();
    await renderPage(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UPDATE_CHECK_INTERVAL_MS * 3);
    });
    expect(screen.getAllByText(/Nueva versión/, { selector: 'p' })).toHaveLength(1);
  });
});

describe('update checks (PWA-4)', () => {
  it('asks for a new worker every 60 minutes', async () => {
    expect(UPDATE_CHECK_INTERVAL_MS).toBe(60 * 60 * 1000);
    vi.useFakeTimers();
    await renderPage();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UPDATE_CHECK_INTERVAL_MS - 1);
    });
    expect(registration.update).not.toHaveBeenCalled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(registration.update).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UPDATE_CHECK_INTERVAL_MS);
    });
    expect(registration.update).toHaveBeenCalledTimes(2);
  });

  it('asks when the window becomes visible again, not when it is hidden', async () => {
    await renderPage();
    setVisibility('hidden');
    expect(registration.update).not.toHaveBeenCalled();
    setVisibility('visible');
    expect(registration.update).toHaveBeenCalledTimes(1);
  });

  it('does not ask while offline', async () => {
    vi.useFakeTimers();
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await renderPage();
    setVisibility('visible');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UPDATE_CHECK_INTERVAL_MS);
    });
    expect(registration.update).not.toHaveBeenCalled();
  });

  it('survives a failed check (the next one still runs)', async () => {
    vi.useFakeTimers();
    registration.update.mockRejectedValueOnce(new Error('offline'));
    await renderPage();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UPDATE_CHECK_INTERVAL_MS * 2);
    });
    expect(registration.update).toHaveBeenCalledTimes(2);
  });

  it('stops checking when the app is unmounted', async () => {
    vi.useFakeTimers();
    const { unmount } = await renderPage();
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(UPDATE_CHECK_INTERVAL_MS * 2);
    });
    setVisibility('visible');
    expect(registration.update).not.toHaveBeenCalled();
  });
});

describe('self-destroying build (PWA-5)', () => {
  it('does not register a worker, or the rollback worker would reinstall itself in a loop', async () => {
    vi.stubEnv('VITE_PWA_SELF_DESTROY', 'true');
    await renderPage(true);
    expect(sw.registerCalls).toBe(0);
    expect(screen.queryByText(/Nueva versión/, { selector: 'p' })).not.toBeInTheDocument();
  });
});
