import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { down } from '@/lib/breakpoints';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';
import { Select } from './Select';

const css = readCss(join(SRC_DIR, 'components/ui/Select.module.css'));
const value = (selector: string, prop: string) =>
  declsFor(css, selector).find((decl) => decl.prop === prop)?.value;

describe('Select (owner feedback S2)', () => {
  it('renders a native combobox with the module class and the caller class', () => {
    render(
      <Select aria-label="Order" className="extra" defaultValue="b">
        <option value="a">A</option>
        <option value="b">B</option>
      </Select>,
    );
    const select = screen.getByRole('combobox', { name: 'Order' });
    expect(select.className).toMatch(/select/);
    expect(select.className).toMatch(/extra/);
    expect(select).toHaveValue('b');
  });

  it('drops the platform look and draws its own arrow', () => {
    expect(value('.select', 'appearance')).toBe('none');
    expect(value('.select', '-webkit-appearance')).toBe('none');
    expect(value('.select', 'background-image')).toMatch(/currentColor/);
    expect(value('.select', 'padding')).toBe('0 34px 0 12px');
  });

  it('uses an opaque dark field and dark options, so the list is readable everywhere', () => {
    expect(value('.select', 'color-scheme')).toBe('dark');
    expect(value('.select', 'background-color')).toBe('var(--bg-1)');
    expect(value('.select option', 'background-color')).toBe('var(--bg-1)');
    expect(value('.select option', 'color')).toBe('var(--text)');
  });

  it('uses 16 px text on phones so iOS does not zoom on focus', () => {
    const phone = rules(css).find(
      (rule) => rule.selectors.includes('.select') && rule.atRules.includes(`media ${down('md')}`),
    );
    expect(phone?.decls).toContainEqual({ prop: 'font-size', value: '16px' });
  });

  it('keeps every rule in the components layer', () => {
    expect(rules(css).every((rule) => rule.atRules.includes('layer components'))).toBe(true);
  });
});
