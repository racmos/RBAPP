import { useEffect } from 'react';

export const PRODUCT_NAME = 'Rift Manager';

/** `<page> · Rift Manager`, or the bare product name for a page without a title (I18N-3). */
export const formatTitle = (page: string | null | undefined): string =>
  page ? `${page} · ${PRODUCT_NAME}` : PRODUCT_NAME;

/** Pass the already translated page title: it changes with the language, so the title does too. */
export function useDocumentTitle(page: string | null | undefined): void {
  useEffect(() => {
    document.title = formatTitle(page);
  }, [page]);
}
