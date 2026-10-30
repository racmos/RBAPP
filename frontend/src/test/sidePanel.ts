import { within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect } from 'vitest';

/**
 * A side panel folds away with its toggle (owner feedback S23): the toggle controls the content
 * inside the region, the region stays (collapsed) and the state is stored under `key`.
 */
export async function expectCollapsible(
  region: HTMLElement,
  names: { hide: string; show: string },
  key: string,
): Promise<void> {
  const toggle = within(region).getByRole('button', { name: names.hide });
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  const content = document.getElementById(toggle.getAttribute('aria-controls') ?? '');
  expect(content).not.toBeNull();
  expect(region).toContainElement(content);
  expect(content).toBeVisible();

  await userEvent.click(toggle);
  expect(within(region).getByRole('button', { name: names.show })).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  expect(content).not.toBeVisible();
  expect(region).toHaveAttribute('data-collapsed');
  expect(localStorage.getItem(key)).toBe('collapsed');
}
