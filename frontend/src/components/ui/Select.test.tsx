import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { Field } from './Field';
import { Select } from './Select';

function Demo({ initial = 'es' }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <Field label="Idioma" hint="Cambia el idioma">
        {(props) => (
          <Select {...props} value={value} onChange={(event) => setValue(event.target.value)}>
            <option value="es">Español</option>
            <option value="en">English</option>
          </Select>
        )}
      </Field>
      <output>{value}</output>
    </>
  );
}

describe('Select (DS-8)', () => {
  it('is a combobox reachable by its Field label and described by the hint', () => {
    render(<Demo />);
    const select = screen.getByRole('combobox', { name: 'Idioma' });
    expect(select).toHaveValue('es');
    expect(select).toHaveAccessibleDescription('Cambia el idioma');
  });

  it('changes value with the keyboard-driven native control', async () => {
    render(<Demo />);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Idioma' }), 'English');
    expect(screen.getByRole('combobox', { name: 'Idioma' })).toHaveValue('en');
    expect(screen.getByRole('status')).toHaveTextContent('en');
  });

  it('can be disabled', () => {
    render(
      <Select aria-label="X" disabled>
        <option>a</option>
      </Select>,
    );
    expect(screen.getByRole('combobox', { name: 'X' })).toBeDisabled();
  });
});
