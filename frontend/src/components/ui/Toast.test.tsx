import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithI18n } from '@/test/i18n';
import { LiveAnnouncer } from './LiveAnnouncer';
import { ToastStack } from './Toast';
import { clearToasts, dismissToast, pushToast } from './toastStore';

beforeEach(() => clearToasts());
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

/** The toast text inside the stack; the live region repeats the message, so scope the query. */
const stack = () => screen.queryByRole('region', { name: 'Notificaciones' });
const inStack = (text: string) => {
  const region = stack();
  return region ? within(region).queryByText(text) : null;
};

const mount = () =>
  renderWithI18n(
    <>
      <LiveAnnouncer />
      <ToastStack />
    </>,
  );

describe('toast store', () => {
  it('assigns increasing ids, and dismiss removes only that toast', async () => {
    await mount();
    let a = 0;
    let b = 0;
    act(() => {
      a = pushToast({ kind: 'info', message: 'Uno' });
      b = pushToast({ kind: 'info', message: 'Dos' });
    });
    expect(b).toBeGreaterThan(a);
    act(() => dismissToast(a));
    expect(inStack('Uno')).not.toBeInTheDocument();
    expect(inStack('Dos')).toBeInTheDocument();
  });
});

describe('ToastStack', () => {
  it('renders nothing while there are no toasts', async () => {
    const { container } = await mount();
    expect(container.querySelector('[popover]')).toBeNull();
  });

  it('shows a toast in a labelled manual popover', async () => {
    const { container } = await mount();
    act(() => void pushToast({ kind: 'success', message: 'Cuenta creada' }));
    expect(inStack('Cuenta creada')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Notificaciones' })).toBe(
      container.querySelector('[popover="manual"]'),
    );
  });

  it('announces the message through the live region', async () => {
    await mount();
    act(() => void pushToast({ kind: 'error', message: 'No se pudo guardar' }));
    expect(screen.getByRole('status')).toHaveTextContent('No se pudo guardar');
  });

  it('re-shows the popover on every push so it stays above open dialogs', async () => {
    const showPopover = vi.spyOn(HTMLElement.prototype, 'showPopover');
    const hidePopover = vi.spyOn(HTMLElement.prototype, 'hidePopover');
    await mount();
    act(() => void pushToast({ kind: 'info', message: 'Uno' }));
    expect(showPopover).toHaveBeenCalledTimes(1);
    act(() => void pushToast({ kind: 'info', message: 'Dos' }));
    expect(showPopover).toHaveBeenCalledTimes(2);
    // hide, then show: that is what moves the popover to the top of the top layer
    const [, secondShow] = showPopover.mock.invocationCallOrder;
    const lastHide = hidePopover.mock.invocationCallOrder.at(-1)!;
    expect(lastHide).toBeLessThan(secondShow);
  });

  it('works without the Popover API (fixed-position fallback)', async () => {
    const { container } = await mount();
    const proto = HTMLElement.prototype as { showPopover?: unknown };
    const original = proto.showPopover;
    proto.showPopover = undefined; // a browser without the Popover API
    try {
      expect(() =>
        act(() => void pushToast({ kind: 'info', message: 'Sin popover' })),
      ).not.toThrow();
      expect(container.querySelector('[popover]')).toHaveTextContent('Sin popover');
    } finally {
      proto.showPopover = original;
    }
  });

  it('runs the action of a focusable button and dismisses the toast', async () => {
    const onAction = vi.fn();
    await mount();
    act(
      () =>
        void pushToast({
          kind: 'error',
          message: 'Falló',
          action: { label: 'Reintentar', onAction },
        }),
    );
    const button = screen.getByRole('button', { name: 'Reintentar' });
    await userEvent.tab();
    expect(button).toHaveFocus();
    await userEvent.click(button);
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(inStack('Falló')).not.toBeInTheDocument();
  });

  it('closes with the close button', async () => {
    await mount();
    act(() => void pushToast({ kind: 'info', message: 'Cierra' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    expect(inStack('Cierra')).not.toBeInTheDocument();
  });

  describe('auto-dismiss', () => {
    it('removes a toast after its duration', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      await mount();
      act(() => void pushToast({ kind: 'info', message: 'Pasajero', duration: 3000 }));
      await act(() => vi.advanceTimersByTimeAsync(2999));
      expect(inStack('Pasajero')).toBeInTheDocument();
      await act(() => vi.advanceTimersByTimeAsync(2));
      expect(inStack('Pasajero')).not.toBeInTheDocument();
    });

    it('does not dismiss a toast under the pointer, and restarts when it leaves', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      await mount();
      act(() => void pushToast({ kind: 'info', message: 'Leyendo', duration: 3000 }));
      const item = inStack('Leyendo')!.closest('[data-toast]') as HTMLElement;
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      await user.hover(item);
      await act(() => vi.advanceTimersByTimeAsync(10_000));
      expect(inStack('Leyendo')).toBeInTheDocument();
      await user.unhover(item);
      await act(() => vi.advanceTimersByTimeAsync(3001));
      expect(inStack('Leyendo')).not.toBeInTheDocument();
    });

    it('does not dismiss a toast that has focus', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      await mount();
      act(
        () =>
          void pushToast({
            kind: 'error',
            message: 'Con foco',
            duration: 3000,
            action: { label: 'Reintentar', onAction: () => {} },
          }),
      );
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      await user.tab();
      expect(screen.getByRole('button', { name: 'Reintentar' })).toHaveFocus();
      await act(() => vi.advanceTimersByTimeAsync(10_000));
      expect(inStack('Con foco')).toBeInTheDocument();
    });

    it('keeps a toast with duration 0 until it is dismissed', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      await mount();
      act(() => void pushToast({ kind: 'error', message: 'Persistente', duration: 0 }));
      await act(() => vi.advanceTimersByTimeAsync(60_000));
      expect(inStack('Persistente')).toBeInTheDocument();
    });
  });
});
