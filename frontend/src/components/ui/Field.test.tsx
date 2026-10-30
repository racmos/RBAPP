import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { Field } from './Field';
import { Select } from './Select';

const LOOK = ['color', 'font-size', 'font-weight', 'letter-spacing', 'text-transform'];
const look = (file: string, selector = '.label') =>
  Object.fromEntries(
    declsFor(readCss(join(SRC_DIR, file)), selector)
      .filter((decl) => LOOK.includes(decl.prop))
      .map((decl) => [decl.prop, decl.value]),
  );

describe('Field labels (owner feedback S18 c)', () => {
  it('names its control, a Select included', () => {
    render(
      <Field label="Set">
        {(control) => (
          <Select {...control}>
            <option value="">Todos</option>
          </Select>
        )}
      </Field>,
    );
    expect(screen.getByRole('combobox', { name: 'Set' })).toBeInTheDocument();
    expect(screen.getByText('Set').tagName).toBe('LABEL');
  });

  it('looks like every other form label: plain case, muted, 13 px', () => {
    const field = look('components/ui/Field.module.css');
    expect(field).toEqual({ color: 'var(--muted)', 'font-size': '13px', 'font-weight': '600' });
    // the card picker and the quantity stepper sit in the same forms
    expect(look('catalog/CardCombobox.module.css')).toEqual(field);
    expect(look('collection/Stepper.module.css')).toEqual(field);
  });
});
