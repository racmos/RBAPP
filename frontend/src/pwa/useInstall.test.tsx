import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithI18n } from '@/test/i18n';
import { setDisplayMode } from '@/test/viewport';
import { InstallItem } from './InstallItem';
import { isIosSafari, listen, resetInstallPrompt } from './installPrompt';

const IPHONE_SAFARI =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
const IPAD_DESKTOP_SAFARI =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15';
const IPHONE_CHROME =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.153 Mobile/15E148 Safari/604.1';
const ANDROID_CHROME =
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36';

type Device = { ua?: string; platform?: string; touch?: number };

/** Pretend to be a device: `navigator.userAgent`, `platform` and `maxTouchPoints`. */
function pretend({ ua = ANDROID_CHROME, platform = 'Linux armv8l', touch = 5 }: Device) {
  vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(ua);
  vi.spyOn(navigator, 'platform', 'get').mockReturnValue(platform);
  // jsdom has no maxTouchPoints, so there is nothing to spy on
  Object.defineProperty(navigator, 'maxTouchPoints', { value: touch, configurable: true });
}

/** The event Chromium fires when the app is installable. */
function installEvent() {
  const event = new Event('beforeinstallprompt', { cancelable: true }) as Event & {
    prompt: ReturnType<typeof vi.fn>;
    userChoice: Promise<{ outcome: string }>;
  };
  event.prompt = vi.fn(() => Promise.resolve());
  event.userChoice = Promise.resolve({ outcome: 'accepted' });
  return event;
}

const fire = (event: Event) => act(() => void window.dispatchEvent(event));

let stopListening: () => void;

beforeEach(() => {
  pretend({});
  stopListening = listen();
});

afterEach(() => {
  stopListening();
  resetInstallPrompt();
  vi.restoreAllMocks();
  Reflect.deleteProperty(navigator, 'standalone');
  Reflect.deleteProperty(navigator, 'maxTouchPoints');
});

describe('isIosSafari (PWA-6)', () => {
  it.each([
    ['iPhone Safari', IPHONE_SAFARI, 'iPhone', 5, true],
    ['iPad Safari in desktop mode (MacIntel with touch)', IPAD_DESKTOP_SAFARI, 'MacIntel', 5, true],
    ['Safari on a Mac (no touch)', IPAD_DESKTOP_SAFARI, 'MacIntel', 0, false],
    ['Chrome on iPhone', IPHONE_CHROME, 'iPhone', 5, false],
    ['Chrome on Android', ANDROID_CHROME, 'Linux armv8l', 5, false],
  ])('%s', (_label, ua, platform, touch, expected) => {
    expect(isIosSafari({ userAgent: ua, platform, maxTouchPoints: touch })).toBe(expected);
  });
});

describe('Install item with the browser prompt (PWA-6)', () => {
  it('is hidden when the browser offers no install path', async () => {
    await renderWithI18n(<InstallItem />);
    expect(screen.queryByRole('button', { name: /instalar/i })).not.toBeInTheDocument();
  });

  it('keeps the event (preventDefault) and shows the item', async () => {
    await renderWithI18n(<InstallItem />);
    const event = installEvent();
    fire(event);
    expect(event.defaultPrevented).toBe(true);
    expect(screen.getByRole('button', { name: 'Instalar app' })).toBeVisible();
  });

  it('calls the saved prompt() when used', async () => {
    await renderWithI18n(<InstallItem />);
    const event = installEvent();
    fire(event);
    await userEvent.click(screen.getByRole('button', { name: 'Instalar app' }));
    expect(event.prompt).toHaveBeenCalledTimes(1);
  });

  it('forgets the event once it was used: a prompt can be shown only once', async () => {
    await renderWithI18n(<InstallItem />);
    fire(installEvent());
    await userEvent.click(screen.getByRole('button', { name: 'Instalar app' }));
    expect(screen.queryByRole('button', { name: 'Instalar app' })).not.toBeInTheDocument();
  });

  it('hides the item when appinstalled fires', async () => {
    await renderWithI18n(<InstallItem />);
    fire(installEvent());
    expect(screen.getByRole('button', { name: 'Instalar app' })).toBeVisible();
    fire(new Event('appinstalled'));
    expect(screen.queryByRole('button', { name: 'Instalar app' })).not.toBeInTheDocument();
  });

  it('catches an event that fired before the item mounted (listen() runs before React)', async () => {
    fire(installEvent());
    await renderWithI18n(<InstallItem />);
    expect(screen.getByRole('button', { name: 'Instalar app' })).toBeVisible();
  });

  it('listens once however many times listen() is called', async () => {
    const stopAgain = listen();
    await renderWithI18n(<InstallItem />);
    const event = installEvent();
    fire(event);
    await userEvent.click(screen.getByRole('button', { name: 'Instalar app' }));
    expect(event.prompt).toHaveBeenCalledTimes(1);
    stopAgain();
  });

  it('says Install in English', async () => {
    await renderWithI18n(<InstallItem />, 'en');
    fire(installEvent());
    expect(screen.getByRole('button', { name: 'Install app' })).toBeVisible();
  });

  it('is hidden in the installed window (display-mode: standalone)', async () => {
    setDisplayMode('standalone');
    await renderWithI18n(<InstallItem />);
    fire(installEvent());
    expect(screen.queryByRole('button', { name: /instalar/i })).not.toBeInTheDocument();
  });

  it('is hidden when the window turns standalone after an install', async () => {
    await renderWithI18n(<InstallItem />);
    fire(installEvent());
    act(() => setDisplayMode('standalone'));
    expect(screen.queryByRole('button', { name: /instalar/i })).not.toBeInTheDocument();
  });

  it('is hidden on iOS when navigator.standalone is set', async () => {
    pretend({ ua: IPHONE_SAFARI, platform: 'iPhone' });
    Object.defineProperty(navigator, 'standalone', { value: true, configurable: true });
    await renderWithI18n(<InstallItem />);
    expect(screen.queryByRole('button', { name: /instalar/i })).not.toBeInTheDocument();
  });
});

describe('Install item on iOS Safari (PWA-6)', () => {
  const iphone = () => pretend({ ua: IPHONE_SAFARI, platform: 'iPhone' });

  it('shows the item without any install event', async () => {
    iphone();
    await renderWithI18n(<InstallItem />);
    expect(screen.getByRole('button', { name: 'Instalar app' })).toBeVisible();
  });

  it('opens the instructions with the Share and Add to Home Screen steps', async () => {
    iphone();
    await renderWithI18n(<InstallItem />);
    await userEvent.click(screen.getByRole('button', { name: 'Instalar app' }));
    const dialog = screen.getByRole('dialog', { name: /Instalar en iPhone o iPad/ });
    expect(within(dialog).getByText(/Compartir/)).toBeVisible();
    expect(within(dialog).getByText(/Añadir a pantalla de inicio/)).toBeVisible();
    expect(within(dialog).getAllByRole('listitem')).toHaveLength(3);
  });

  it('has no axe violations with the instructions open (F1 unit g)', async () => {
    iphone();
    await renderWithI18n(<InstallItem />);
    await userEvent.click(screen.getByRole('button', { name: 'Instalar app' }));
    expect(screen.getByRole('dialog', { name: /Instalar en iPhone o iPad/ })).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('closes with Escape and returns focus to the item', async () => {
    iphone();
    await renderWithI18n(<InstallItem />);
    const item = screen.getByRole('button', { name: 'Instalar app' });
    await userEvent.click(item);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(item).toHaveFocus();
  });

  it('says the steps in English', async () => {
    iphone();
    await renderWithI18n(<InstallItem />, 'en');
    await userEvent.click(screen.getByRole('button', { name: 'Install app' }));
    const dialog = screen.getByRole('dialog', { name: /Install on iPhone or iPad/ });
    expect(within(dialog).getByText(/Share/)).toBeVisible();
    expect(within(dialog).getByText(/Add to Home Screen/)).toBeVisible();
  });

  it('prefers the browser prompt when there is one', async () => {
    iphone();
    await renderWithI18n(<InstallItem />);
    const event = installEvent();
    fire(event);
    await userEvent.click(screen.getByRole('button', { name: 'Instalar app' }));
    expect(event.prompt).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('shows no item on Chrome for iOS, which has no install path in F1', async () => {
    pretend({ ua: IPHONE_CHROME, platform: 'iPhone' });
    await renderWithI18n(<InstallItem />);
    expect(screen.queryByRole('button', { name: /instalar/i })).not.toBeInTheDocument();
  });
});
