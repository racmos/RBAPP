import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Field } from './Field';
import { Input } from './Input';

const ids = (element: HTMLElement) =>
  (element.getAttribute('aria-describedby') ?? '').split(' ').filter(Boolean);

describe('Field (DS-8)', () => {
  it('makes the input reachable by its label text', () => {
    render(<Field label="Usuario">{(props) => <Input {...props} />}</Field>);
    expect(screen.getByLabelText('Usuario')).toBeInstanceOf(HTMLInputElement);
  });

  it('references the hint through aria-describedby', () => {
    render(
      <Field label="Usuario" hint="3 a 32 caracteres">
        {(props) => <Input {...props} />}
      </Field>,
    );
    const input = screen.getByLabelText('Usuario');
    const hint = screen.getByText('3 a 32 caracteres');
    expect(ids(input)).toEqual([hint.id]);
    expect(input).not.toHaveAttribute('aria-invalid');
  });

  it('references both the hint and the error, and marks the input invalid', () => {
    render(
      <Field label="Correo" hint="Usa tu correo" error="Correo no válido">
        {(props) => <Input {...props} />}
      </Field>,
    );
    const input = screen.getByLabelText('Correo');
    const hint = screen.getByText('Usa tu correo');
    const error = screen.getByText('Correo no válido');
    expect(hint.id).not.toBe(error.id);
    expect(ids(input)).toEqual([hint.id, error.id]);
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });

  it('has no aria-describedby when there is nothing to describe', () => {
    render(<Field label="Usuario">{(props) => <Input {...props} />}</Field>);
    expect(screen.getByLabelText('Usuario')).not.toHaveAttribute('aria-describedby');
  });

  it('gives two fields different ids', () => {
    render(
      <>
        <Field label="Uno">{(props) => <Input {...props} />}</Field>
        <Field label="Dos">{(props) => <Input {...props} />}</Field>
      </>,
    );
    expect(screen.getByLabelText('Uno').id).not.toBe(screen.getByLabelText('Dos').id);
  });

  it('marks a required field for assistive technology', () => {
    render(
      <Field label="Usuario" required>
        {(props) => <Input {...props} />}
      </Field>,
    );
    expect(screen.getByLabelText(/Usuario/)).toBeRequired();
  });
});
