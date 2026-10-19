import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { renderWithI18n } from '@/test/i18n';
import { Field } from './Field';
import { PasswordInput } from './PasswordInput';

describe('PasswordInput', () => {
  it('hides the password and offers a named control to show it', async () => {
    await renderWithI18n(
      <Field label="Contraseña">{(props) => <PasswordInput {...props} />}</Field>,
    );
    const input = screen.getByLabelText('Contraseña');
    expect(input).toHaveAttribute('type', 'password');
    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }));
    expect(input).toHaveAttribute('type', 'text');
    await userEvent.click(screen.getByRole('button', { name: 'Ocultar contraseña' }));
    expect(input).toHaveAttribute('type', 'password');
  });

  it('names the control in the active language', async () => {
    await renderWithI18n(
      <Field label="Password">{(props) => <PasswordInput {...props} />}</Field>,
      'en',
    );
    expect(screen.getByRole('button', { name: 'Show password' })).toBeVisible();
  });

  it('passes autocomplete through', async () => {
    await renderWithI18n(
      <Field label="Nueva">
        {(props) => <PasswordInput {...props} autoComplete="new-password" />}
      </Field>,
    );
    expect(screen.getByLabelText('Nueva')).toHaveAttribute('autocomplete', 'new-password');
  });

  it('keeps the typed value when toggling visibility', async () => {
    await renderWithI18n(
      <Field label="Contraseña">{(props) => <PasswordInput {...props} />}</Field>,
    );
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secreto');
    await userEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña' }));
    expect(screen.getByLabelText('Contraseña')).toHaveValue('secreto');
  });

  it('keeps the visibility control out of the way of focus order issues: it is a real button', async () => {
    await renderWithI18n(
      <Field label="Contraseña">{(props) => <PasswordInput {...props} />}</Field>,
    );
    expect(screen.getByRole('button', { name: 'Mostrar contraseña' })).toHaveAttribute(
      'type',
      'button',
    );
  });
});
