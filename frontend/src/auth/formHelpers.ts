import type { i18n as I18n } from 'i18next';
import { useEffect, useState, type RefObject } from 'react';
import type { ErrorDetail } from '@/api/types';
import { translateDetail } from '@/i18n';

export type FieldErrors<Name extends string> = Partial<Record<Name, string>>;

/** Server `details[]` -> translated text per known field (the first message of a field wins). */
export function fieldErrorsFromDetails<Name extends string>(
  details: readonly ErrorDetail[],
  i18n: I18n,
  fields: readonly Name[],
): FieldErrors<Name> {
  const errors: FieldErrors<Name> = {};
  for (const detail of details) {
    const field = fields.find((name) => name === detail.field);
    if (field && errors[field] === undefined) errors[field] = translateDetail(detail, i18n);
  }
  return errors;
}

/**
 * Move focus after a failed submit (FAUTH-10): to a named control or to the first
 * `aria-invalid` one. The move happens in an effect, once the new error state has rendered.
 */
export function useFormFocus(form: RefObject<HTMLFormElement | null>) {
  const [target, setTarget] = useState<{ name: string | null; tick: number }>({
    name: null,
    tick: 0,
  });

  useEffect(() => {
    if (target.tick === 0 || !form.current) return;
    const element = target.name
      ? form.current.elements.namedItem(target.name)
      : form.current.querySelector('[aria-invalid="true"]');
    if (element instanceof HTMLElement) element.focus();
  }, [target, form]);

  return {
    request: (name: string | null = null) =>
      setTarget((previous) => ({ name, tick: previous.tick + 1 })),
  };
}
