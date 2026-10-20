// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';

describe('modal scroll lock (D17)', () => {
  it('locks the page scroll while a dialog is open', () => {
    const decls = declsFor(readCss(join(SRC_DIR, 'styles', 'base.css')), 'html:has(dialog[open])');
    expect(decls).toContainEqual({ prop: 'overflow', value: 'hidden' });
  });
});
