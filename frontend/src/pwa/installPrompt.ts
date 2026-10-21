/**
 * The browser's install prompt (PWA-6). Chromium fires `beforeinstallprompt` once the app is
 * installable; the event must be kept and can be shown once, from a user gesture. It is a module
 * store started in `main.tsx` before React renders, so an event that fires early is not lost.
 */
export type InstallChoice = { outcome: 'accepted' | 'dismissed'; platform?: string };
export type BeforeInstallPromptEvent = Event & {
  prompt(): Promise<void>;
  userChoice: Promise<InstallChoice>;
};

let saved: BeforeInstallPromptEvent | null = null;
let stop: (() => void) | null = null;
const listeners = new Set<() => void>();

const emit = () => listeners.forEach((listener) => listener());

const onBeforeInstallPrompt = (event: Event) => {
  event.preventDefault(); // no mini-infobar: the item in the menu is the way in
  saved = event as BeforeInstallPromptEvent;
  emit();
};
const onInstalled = () => {
  saved = null;
  emit();
};

/** Start listening (once, however often it is called). Returns the function that stops it. */
export function listen(): () => void {
  if (!stop) {
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.addEventListener('appinstalled', onInstalled);
    stop = () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
      window.removeEventListener('appinstalled', onInstalled);
      stop = null;
    };
  }
  return stop;
}

export const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};
export const getSavedPrompt = (): BeforeInstallPromptEvent | null => saved;

/**
 * Show the browser's prompt. The event is spent once used, so the item hides until the browser
 * offers the install again. Returns false when there was nothing to show.
 */
export async function promptInstall(): Promise<boolean> {
  const event = saved;
  if (!event) return false;
  saved = null;
  emit();
  await event.prompt();
  return true;
}

/** Forget the saved event (tests, and a clean slate after `listen()` is stopped). */
export function resetInstallPrompt(): void {
  saved = null;
  emit();
}

type NavigatorLike = Pick<Navigator, 'userAgent' | 'platform' | 'maxTouchPoints'>;

/**
 * iPhone, iPad (also when it asks for desktop sites and reports `MacIntel` with a touch screen)
 * or iPod, in Safari. iOS has no install event: the user adds the app from the Share menu.
 */
export function isIosSafari({ userAgent, platform, maxTouchPoints }: NavigatorLike): boolean {
  const iosDevice =
    /iPhone|iPad|iPod/.test(userAgent) || (platform === 'MacIntel' && maxTouchPoints > 1);
  const safari =
    /Safari/.test(userAgent) && !/CriOS|FxiOS|EdgiOS|OPiOS|OPT\/|Chrome|Android/.test(userAgent);
  return iosDevice && safari;
}
