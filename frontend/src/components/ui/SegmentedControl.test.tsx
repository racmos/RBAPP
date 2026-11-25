import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';
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

describe('SegmentedControl counts and keys (CM-l)', () => {
  const VIEWS = [
    { value: 'all', label: 'All links' },
    { value: 'conflicts', label: 'Conflicts', count: 2, tone: 'warning' },
    { value: 'ignored', label: 'Ignored', count: 0 },
  ] as const;

  it('shows the count of an option next to its label and in its accessible name', async () => {
    const { container } = render(
      <SegmentedControl label="Linked view" options={VIEWS} value="all" onChange={() => {}} />,
    );
    const conflicts = screen.getByRole('radio', { name: 'Conflicts 2' });
    expect(conflicts).not.toBeChecked();
    expect(screen.getByRole('radio', { name: 'Ignored 0' })).toBeVisible();
    // an option without a count has no count element
    expect(screen.getByRole('radio', { name: 'All links' })).toBeChecked();
    const counts = container.querySelectorAll('[data-count]');
    expect([...counts].map((count) => count.textContent)).toEqual(['2', '0']);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('marks a count with its tone, the plain tone by default', () => {
    const { container } = render(
      <SegmentedControl label="Linked view" options={VIEWS} value="all" onChange={() => {}} />,
    );
    const [warning, plain] = container.querySelectorAll('[data-count]');
    expect(warning).toHaveAttribute('data-tone', 'warning');
    expect(plain).toHaveAttribute('data-tone', 'neutral');
  });

  it('arrow keys move the choice between the options', async () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl label="Linked view" options={VIEWS} value="all" onChange={onChange} />,
    );
    screen.getByRole('radio', { name: 'All links' }).focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(onChange).toHaveBeenLastCalledWith('conflicts');
    expect(screen.getByRole('radio', { name: 'Conflicts 2' })).toHaveFocus();
  });

  it('draws the focus on the visible segment and colours the warning count', () => {
    const css = readCss(join(SRC_DIR, 'components/ui/SegmentedControl.module.css'));
    expect(declsFor(css, '.input:focus-visible + .text')).toContainEqual({
      prop: 'outline',
      value: '2px solid var(--accent)',
    });
    expect(declsFor(css, ".count[data-tone='warning']")).toContainEqual({
      prop: 'color',
      value: 'var(--gold)',
    });
  });
});
