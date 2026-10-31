import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';
import { Checkbox } from './Checkbox';

const css = readCss(join(SRC_DIR, 'components/ui/Checkbox.module.css'));
const value = (selector: string, prop: string) =>
  declsFor(css, selector).find((decl) => decl.prop === prop)?.value;

describe('Checkbox as a toggle button (owner feedback S3, S7)', () => {
  it('keeps a real checkbox named by its label that toggles on click', async () => {
    const onChange = vi.fn();
    render(<Checkbox label="OGN" onChange={onChange} />);
    const box = screen.getByRole('checkbox', { name: 'OGN' });
    expect(box).not.toBeChecked();
    await userEvent.click(screen.getByText('OGN'));
    expect(box).toBeChecked();
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('toggles with the keyboard', async () => {
    render(<Checkbox label="OGN" />);
    await userEvent.tab();
    expect(screen.getByRole('checkbox', { name: 'OGN' })).toHaveFocus();
    await userEvent.keyboard(' ');
    expect(screen.getByRole('checkbox', { name: 'OGN' })).toBeChecked();
  });

  it('draws a check mark as the non-colour cue of the checked state', () => {
    const { container } = render(<Checkbox label="OGN" defaultChecked />);
    const tick = container.querySelector('[data-slot="checkbox-tick"]');
    expect(tick).not.toBeNull();
    expect(tick?.getAttribute('aria-hidden')).toBe('true');
    expect(tick?.querySelector('svg')).not.toBeNull();
  });

  it('can hide its label and keep it as the accessible name', () => {
    render(<Checkbox label="Select the page" hideLabel />);
    expect(screen.getByRole('checkbox', { name: 'Select the page' })).toBeInTheDocument();
    expect(screen.getByText('Select the page')).toHaveClass('sr-only');
  });

  it('shows the mixed state', () => {
    render(<Checkbox label="All" indeterminate />);
    expect((screen.getByRole('checkbox', { name: 'All' }) as HTMLInputElement).indeterminate).toBe(
      true,
    );
  });

  it('keeps disabled and the input props', () => {
    render(<Checkbox label="OGN" disabled name="set" value="OGN" />);
    const box = screen.getByRole('checkbox', { name: 'OGN' });
    expect(box).toBeDisabled();
    expect(box).toHaveAttribute('name', 'set');
  });

  it('lights up when checked: accent fill, readable ink and a glow', () => {
    expect(value('.input:checked + .face', 'background')).toBe('var(--accent)');
    expect(value('.input:checked + .face', 'color')).toBe('var(--accent-ink)');
    expect(value('.input:checked + .face', 'box-shadow')).toMatch(/var\(--accent-glow\)/);
  });

  it('hides the native box but keeps it clickable over the whole button', () => {
    expect(value('.input', 'opacity')).toBe('0');
    expect(value('.input', 'position')).toBe('absolute');
    expect(value('.input', 'inset')).toBe('0');
  });

  it('shows the keyboard focus on the button face', () => {
    expect(value('.input:focus-visible + .face', 'outline')).toMatch(/var\(--accent\)/);
  });

  it('keeps every rule in the components layer', () => {
    expect(rules(css).every((rule) => rule.atRules.includes('layer components'))).toBe(true);
  });

  it('has no axe violations', async () => {
    const { container } = render(
      <>
        <Checkbox label="OGN" defaultChecked />
        <Checkbox label="SFD" hideLabel />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
