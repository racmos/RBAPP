import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { SRC_DIR, readCss, rules } from '@/test/css';
import { SegmentedControl } from './SegmentedControl';

const OPTIONS = [
  { value: 'any', label: 'Da igual' },
  { value: 'yes', label: 'Sí' },
  { value: 'no', label: 'No' },
] as const;

describe('SegmentedControl visible label (owner feedback S24)', () => {
  it('shows its label above the options and is named by it', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <SegmentedControl
        label="En venta"
        showLabel
        options={OPTIONS}
        value="any"
        onChange={onChange}
      />,
    );
    const group = screen.getByRole('radiogroup', { name: 'En venta' });
    const label = screen.getByText('En venta');
    expect(label).toBeVisible();
    expect(label).not.toHaveClass('sr-only');
    expect(group).toHaveAttribute('aria-labelledby', label.id);
    expect(group).not.toHaveAttribute('aria-label');
    await userEvent.click(screen.getByText('Sí'));
    expect(onChange).toHaveBeenCalledWith('yes');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('without showLabel keeps the name for assistive technology only', () => {
    render(<SegmentedControl label="Vista" options={OPTIONS} value="any" onChange={() => {}} />);
    expect(screen.getByRole('radiogroup', { name: 'Vista' })).toHaveAttribute(
      'aria-label',
      'Vista',
    );
    expect(screen.queryByText('Vista')).toBeNull();
  });

  it('keeps every rule in the components layer', () => {
    const css = readCss(join(SRC_DIR, 'components/ui/SegmentedControl.module.css'));
    expect(rules(css).every((rule) => rule.atRules.includes('layer components'))).toBe(true);
  });
});
