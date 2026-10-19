/**
 * jsdom hides every `[popover]` and has no Popover API. Add the minimum so a shown popover is
 * visible and exposed to the accessibility tree, as in a browser.
 */
export function installPopoverPolyfill(): void {
  const proto = HTMLElement.prototype;
  if (typeof proto.showPopover === 'function') return;
  proto.showPopover = function showPopover(this: HTMLElement) {
    this.style.display = 'block';
  };
  proto.hidePopover = function hidePopover(this: HTMLElement) {
    this.style.display = '';
  };
}
