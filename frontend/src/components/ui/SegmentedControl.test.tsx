import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { SRC_DIR, readCss, rules } from '@/test/css';
import { SegmentedControl } from './SegmentedControl';

const OPTIONS = [
  { value: 'any', label: 'Any' },
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
] as const;

describe('SegmentedControl visible label (owner feedback S24)', () => {
  it('shows its label above the options and is named by it', async () => {
    const onChange = vi.fn();
    const { container } = render(
      <SegmentedControl
        label="On sale"
        showLabel
        options={OPTIONS}
        value="any"
        onChange={onChange}
      />,
    );
    const group = screen.getByRole('radiogroup', { name: 'On sale' });
    const label = screen.getByText('On sale');
    expect(label).toBeVisible();
    expect(label).not.toHaveClass('sr-only');
    expect(group).toHaveAttribute('aria-labelledby', label.id);
    expect(group).not.toHaveAttribute('aria-label');
    await userEvent.click(screen.getByText('Yes'));
    expect(onChange).toHaveBeenCalledWith('yes');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('without showLabel keeps the name for assistive technology only', () => {
    render(<SegmentedControl label="View" options={OPTIONS} value="any" onChange={() => {}} />);
    expect(screen.getByRole('radiogroup', { name: 'View' })).toHaveAttribute('aria-label', 'View');
    expect(screen.queryByText('View')).toBeNull();
  });

  it('keeps every rule in the components layer', () => {
    const css = readCss(join(SRC_DIR, 'components/ui/SegmentedControl.module.css'));
    expect(rules(css).every((rule) => rule.atRules.includes('layer components'))).toBe(true);
  });
});
