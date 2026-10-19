// The only module that imports the library: it stays in the lazy register chunk (D22, FAUTH-3).
import 'altcha';
import { useLayoutEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { AltchaState, AltchaStateChange } from './altcha';

type AltchaWidgetProps = {
  challenge: Record<string, unknown>;
  /** Called on every state change; `payload` is set when `state` is `verified`. */
  onState: (state: AltchaState, payload?: string) => void;
};

/**
 * The ALTCHA proof-of-work widget. The parent remounts it with a new `key` to reset it, because
 * a payload can be used once and the library cannot refetch a preloaded challenge.
 */
export function AltchaWidget({ challenge, onState }: AltchaWidgetProps) {
  const { t } = useTranslation('auth');
  const element = useRef<HTMLElement>(null);
  const latest = useRef(onState);
  useLayoutEffect(() => {
    latest.current = onState;
  });

  // Attach before the widget starts solving, so no state change is missed.
  useLayoutEffect(() => {
    const widget = element.current;
    if (!widget) return;
    const listener = (event: Event) => {
      const { state, payload } = (event as CustomEvent<AltchaStateChange>).detail;
      latest.current(state, payload);
    };
    widget.addEventListener('statechange', listener);
    return () => widget.removeEventListener('statechange', listener);
  }, []);

  const strings = useMemo(
    () =>
      JSON.stringify({
        ariaLinkLabel: t('altcha.ariaLinkLabel'),
        enterCode: t('altcha.enterCode'),
        enterCodeAria: t('altcha.enterCodeAria'),
        error: t('altcha.error'),
        expired: t('altcha.expired'),
        footer: t('altcha.footer'),
        getAudioChallenge: t('altcha.getAudioChallenge'),
        label: t('altcha.label'),
        loading: t('altcha.loading'),
        reload: t('altcha.reload'),
        verificationRequired: t('altcha.verificationRequired'),
        verified: t('altcha.verified'),
        verifying: t('altcha.verifying'),
        waitAlert: t('altcha.waitAlert'),
      }),
    [t],
  );

  return (
    <altcha-widget
      ref={element}
      challengejson={JSON.stringify(challenge)}
      auto="onload"
      hidelogo
      strings={strings}
    />
  );
}
