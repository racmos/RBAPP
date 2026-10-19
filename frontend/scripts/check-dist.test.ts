// @vitest-environment node
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const script = fileURLToPath(new URL('./check-dist.mjs', import.meta.url));

function dist(files: Record<string, string>) {
  const dir = mkdtempSync(join(tmpdir(), 'dist-'));
  for (const [name, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    writeFileSync(join(dir, name), content);
  }
  return dir;
}

const run = (dir: string) => spawnSync('node', [script, dir], { encoding: 'utf8' });
const INDEX = '<!doctype html><title>Rift Manager</title>';

describe('check-dist.mjs (CI-5, CI-9, DS-6)', () => {
  it('passes with only index.html', () => {
    const result = run(dist({ 'index.html': INDEX }));
    expect(result.status).toBe(0);
  });

  it('passes with hashed assets that reference no third-party host', () => {
    const result = run(
      dist({
        'index.html': INDEX,
        'assets/app-abc.js': 'console.log("hi")',
        'assets/app-abc.css': 'body{color:red}',
      }),
    );
    expect(result.status).toBe(0);
  });

  it('fails when index.html is missing', () => {
    const result = run(dist({ 'assets/app.js': '1' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('index.html');
  });

  it('fails on a source map, even in a subfolder', () => {
    const result = run(dist({ 'index.html': INDEX, 'assets/app.js.map': '{}' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('assets/app.js.map');
  });

  it('fails on a .env file', () => {
    const result = run(dist({ 'index.html': INDEX, '.env': 'SECRET=1' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('.env');
  });

  it.each([
    ['index.html', 'index.html', '<link href="https://fonts.googleapis.com/css2?family=Manrope">'],
    ['a css file', 'assets/a.css', '@import url(https://fonts.gstatic.com/s/x.woff2);'],
    ['a js file', 'assets/a.js', 'fetch("https://fonts.googleapis.com/css")'],
  ])('fails on a Google Fonts reference in %s', (_label, file, content) => {
    const result = run(dist({ 'index.html': INDEX, [file]: content }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(file);
  });

  it('passes when the cascade layers first appear in the declared order (D15)', () => {
    const css =
      '@layer reset{a{b:c}}@layer tokens{a{b:c}}@layer base{a{b:c}}@layer layout;@layer components{a{b:c}}@layer reset{a{b:c}}';
    expect(run(dist({ 'index.html': INDEX, 'assets/a.css': css })).status).toBe(0);
  });

  it('fails when a layer first appears before one that must precede it', () => {
    // a component module imported before the stylesheet fixes the wrong order
    const css = '@layer components{a{b:c}}@layer reset{a{b:c}}';
    const result = run(dist({ 'index.html': INDEX, 'assets/a.css': css }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('assets/a.css');
    expect(result.stderr).toContain('layer');
  });

  it('fails when the directory does not exist', () => {
    const result = run(join(tmpdir(), 'dist-does-not-exist'));
    expect(result.status).toBe(1);
  });
});
