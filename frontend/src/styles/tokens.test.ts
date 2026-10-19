// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';

const styles = (file: string) => readCss(join(SRC_DIR, 'styles', file));
const tokens = styles('tokens.css');
const base = styles('base.css');

/** Last declaration wins, like the cascade within one origin and specificity. */
const toMap = (decls: { prop: string; value: string }[]) =>
  Object.fromEntries(decls.map(({ prop, value }) => [prop, value]));
const root = toMap(declsFor(tokens, ':root'));

// Transcribed from openspec/design-handoff.md section 1.1 (DS-1).
const HANDOFF: Record<string, string> = {
  '--bg-0': '#06222c',
  '--bg-1': '#0a2e3a',
  '--panel': 'rgba(13, 58, 73, 0.66)',
  '--panel-2': 'rgba(9, 42, 55, 0.82)',
  '--panel-3': 'rgba(7, 34, 45, 0.92)',
  '--header': 'rgba(6, 26, 34, 0.78)',
  '--line': 'rgba(120, 205, 228, 0.16)',
  '--line-2': 'rgba(120, 205, 228, 0.1)',
  '--cyan': '#2ec6e6',
  '--cyan-bright': '#5fe0ff',
  '--cyan-dim': '#1c8aa6',
  '--orange': '#e8862e',
  '--orange-bright': '#ff9d3f',
  '--red': '#dc4a31',
  '--green': '#33b27b',
  '--gold': '#e0b94a',
  '--text': '#eaf7fb',
  '--muted': '#a6c7d2',
  '--radius': '14px',
  '--radius-sm': '9px',
  '--gap': '20px',
  '--pad': '18px',
  '--row-h': '54px',
  '--maxw': '1280px',
  '--maxw-wide': '1760px',
  '--font-ui': "'Manrope Variable', system-ui, sans-serif",
  '--font-display': "'Space Grotesk Variable', 'Manrope Variable', sans-serif",
  '--shadow': '0 18px 50px -20px rgba(0, 0, 0, 0.6)',
  '--shadow-pop': '0 30px 80px -20px rgba(0, 0, 0, 0.75)',
};

// DS-1 z scale; --z-bg is the background layer of DS-5.
const Z_SCALE: Record<string, string> = {
  '--z-bg': '-2',
  '--z-popover': '30',
  '--z-topbar': '40',
  '--z-botnav': '50',
  '--z-modal': '80',
  '--z-toast': '90',
};

// DS-7: values that replace the handoff colours failing 4.5:1 (contrast.test.ts proves the ratios).
const CONTRAST_FIXES: Record<string, string> = {
  '--muted-2': '#7ca4b1',
  '--red-text': '#ff8a72',
  '--red-strong': '#c43d26',
  '--on-red': '#ffffff',
};

describe('tokens.css :root (DS-1)', () => {
  it.each(Object.entries(HANDOFF))('defines %s as %s', (name, value) => {
    expect(root[name]).toBe(value);
  });

  it.each(Object.entries(Z_SCALE))('defines the z-index %s as %s', (name, value) => {
    expect(root[name]).toBe(value);
  });

  it.each(Object.entries(CONTRAST_FIXES))('applies the contrast fix %s: %s', (name, value) => {
    expect(root[name]).toBe(value);
  });

  it('replaces the failing muted-2 of the prototype', () => {
    expect(root['--muted-2']).not.toBe('#6f96a3');
  });

  it('declares color-scheme: dark', () => {
    expect(root['color-scheme']).toBe('dark');
  });

  it('keeps the default accent on orange with its ink', () => {
    expect(root['--accent']).toBe('var(--orange)');
    expect(root['--accent-ink']).toBe('#160d03');
  });
});

describe('scrollbars (handoff 1.3)', () => {
  it('styles WebKit scrollbars 10x10 with a translucent thumb', () => {
    const bar = toMap(declsFor(base, '::-webkit-scrollbar'));
    expect(bar).toMatchObject({ width: '10px', height: '10px' });
    expect(toMap(declsFor(base, '::-webkit-scrollbar-thumb'))).toMatchObject({
      background: 'rgba(120, 205, 228, 0.18)',
      'border-radius': '20px',
    });
    expect(toMap(declsFor(base, '::-webkit-scrollbar-track'))).toMatchObject({
      background: 'transparent',
    });
  });

  it('reserves the gutter and themes Firefox scrollbars', () => {
    expect(toMap(declsFor(base, 'html'))).toMatchObject({
      'scrollbar-gutter': 'stable',
      'scrollbar-color': 'rgba(120, 205, 228, 0.18) transparent',
    });
  });
});
