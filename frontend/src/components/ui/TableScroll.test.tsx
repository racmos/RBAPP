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
