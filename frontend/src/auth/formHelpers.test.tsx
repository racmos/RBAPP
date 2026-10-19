import { render } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it } from 'vitest';
import { act } from '@testing-library/react';
import { createI18n } from '@/i18n';
import { fieldErrorsFromDetails, useFormFocus } from './formHelpers';

describe('fieldErrorsFromDetails', () => {
  it('translates each detail onto its field and keeps the first one per field', async () => {
    const i18n = await createI18n('es');
    const errors = fieldErrorsFromDetails(
      [
        { field: 'password', message: 'x', type: 't', code: 'too_short', params: { min: 8 } },
        { field: 'password', message: 'y', type: 't', code: 'too_long', params: { max: 128 } },
        { field: 'email', message: 'z', type: 't', code: 'invalid_format' },
      ],
      i18n,
      ['password', 'email', 'username'],
    );
    expect(errors).toEqual({
      password: 'La contraseña debe tener al menos 8 caracteres.',
      email: 'Introduce un correo electrónico válido.',
    });
  });

  it('ignores fields the form does not have', async () => {
    const i18n = await createI18n('es');
    const errors = fieldErrorsFromDetails(
      [{ field: 'altcha', message: 'x', type: 't', code: 'required' }],
      i18n,
      ['username'],
    );
    expect(errors).toEqual({});
  });
});

function Form({ onReady }: { onReady: (focus: ReturnType<typeof useFormFocus>) => void }) {
  const form = useRef<HTMLFormElement>(null);
  const focus = useFormFocus(form);
  onReady(focus);
  return (
    <form ref={form}>
      <input name="a" aria-label="a" />
      <input name="b" aria-label="b" aria-invalid="true" />
      <input name="c" aria-label="c" aria-invalid="true" />
    </form>
  );
}

describe('useFormFocus', () => {
  it('focuses the first invalid field when asked without a name', () => {
    let focus!: ReturnType<typeof useFormFocus>;
    const { getByLabelText } = render(<Form onReady={(f) => (focus = f)} />);
    act(() => focus.request());
    expect(getByLabelText('b')).toHaveFocus();
  });

  it('focuses a named field', () => {
    let focus!: ReturnType<typeof useFormFocus>;
    const { getByLabelText } = render(<Form onReady={(f) => (focus = f)} />);
    act(() => focus.request('c'));
    expect(getByLabelText('c')).toHaveFocus();
  });

  it('refocuses on a repeated request', () => {
    let focus!: ReturnType<typeof useFormFocus>;
    const { getByLabelText } = render(<Form onReady={(f) => (focus = f)} />);
    act(() => focus.request('a'));
    getByLabelText('c').focus();
    act(() => focus.request('a'));
    expect(getByLabelText('a')).toHaveFocus();
  });
});
