import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';
import { TableScroll } from './TableScroll';

const css = readCss(join(SRC_DIR, 'components/ui/TableScroll.module.css'));
const value = (selector: string, prop: string) =>
  declsFor(css, selector).find((decl) => decl.prop === prop)?.value;

describe('TableScroll (owner feedback S1)', () => {
  it('wraps the table and keeps the caller class', () => {
    render(
      <TableScroll className="extra">
        <table>
          <tbody>
            <tr>
              <td>cell</td>
            </tr>
          </tbody>
        </table>
      </TableScroll>,
    );
    const box = screen.getByRole('table').parentElement!;
    expect(box.dataset.slot).toBe('table-scroll');
    expect(box.className).toMatch(/extra/);
  });

  it('is the scroll box in both directions, capped below the topbar', () => {
    expect(value('.scroll', 'overflow')).toBe('auto');
    expect(value('.scroll', 'max-height')).toMatch(/100dvh/);
  });

  it('sticks the header to the top of its own box, opaque and above the rows', () => {
    expect(value('.scroll thead th', 'position')).toBe('sticky');
    expect(value('.scroll thead th', 'top')).toBe('0');
    expect(Number(value('.scroll thead th', 'z-index'))).toBeGreaterThanOrEqual(2);
    expect(value('.scroll thead th', 'background')).toBe('var(--table-head)');
  });

  it('fit mode scrolls with the page: no vertical cap, no scroll box (owner feedback S11)', () => {
    render(
      <TableScroll fit>
        <table>
          <tbody>
            <tr>
              <td>cell</td>
            </tr>
          </tbody>
        </table>
      </TableScroll>,
    );
    const box = screen.getByRole('table').parentElement!;
    expect(box.dataset.slot).toBe('table-scroll');
    expect(box).toHaveAttribute('data-fit');
    expect(box.className).toMatch(/fit/);
    expect(box.className).not.toMatch(/scroll/);
    // `clip` is not a scroll container, so the sticky header sticks to the page.
    expect(value('.fit', 'overflow-x')).toBe('clip');
    expect(value('.fit', 'overflow-y')).toBe('visible');
    expect(value('.fit', 'overflow')).toBeUndefined();
    expect(value('.fit', 'max-height')).toBeUndefined();
  });

  it('fit mode sticks the header below the topbar, opaque and above the rows', () => {
    expect(value('.fit thead', 'position')).toBe('sticky');
    expect(value('.fit thead', 'top')).toBe('calc(64px + var(--safe-top))');
    expect(Number(value('.fit thead', 'z-index'))).toBeGreaterThanOrEqual(2);
    expect(value('.fit thead th', 'background')).toBe('var(--table-head)');
    expect(value('.fit thead th', 'position')).toBeUndefined();
  });

  it('the default box keeps no fit marker', () => {
    render(
      <TableScroll>
        <table>
          <tbody>
            <tr>
              <td>cell</td>
            </tr>
          </tbody>
        </table>
      </TableScroll>,
    );
    const box = screen.getByRole('table').parentElement!;
    expect(box).not.toHaveAttribute('data-fit');
    expect(box.className).toMatch(/scroll/);
  });

  it('keeps every rule in the components layer', () => {
    expect(rules(css).every((rule) => rule.atRules.includes('layer components'))).toBe(true);
  });

  it('defines --table-head as an opaque colour', () => {
    const tokens = readCss(join(SRC_DIR, 'styles/tokens.css'));
    expect(declsFor(tokens, ':root').find((decl) => decl.prop === '--table-head')?.value).toMatch(
      /^#[0-9a-f]{6}$/i,
    );
  });
});
