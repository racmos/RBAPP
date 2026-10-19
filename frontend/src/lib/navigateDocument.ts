/** A full page load, for legacy Jinja pages that live outside the router. Isolated so tests can mock it. */
export function navigateDocument(href: string): void {
  window.location.assign(href);
}
