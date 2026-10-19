/**
 * A stand-in for the `<altcha-widget>` custom element, so register tests control its state:
 * the real widget solves a proof of work in workers, which jsdom does not have.
 */
export class AltchaStub extends HTMLElement {}

export function installAltchaStub(): void {
  if (!customElements.get('altcha-widget')) customElements.define('altcha-widget', AltchaStub);
}

export type AltchaState = 'unverified' | 'verifying' | 'verified' | 'expired' | 'error';

/** Fire the widget's `statechange` event the way altcha 2.3.0 does. */
export function setAltchaState(widget: Element, state: AltchaState, payload?: string): void {
  widget.dispatchEvent(new CustomEvent('statechange', { detail: { state, payload } }));
}
