import { join } from 'node:path';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { renderWithI18n } from '@/test/i18n';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';
import { SidePanel } from './SidePanel';

const css = readCss(join(SRC_DIR, 'components/ui/SidePanel.module.css'));
const value = (selector: string, prop: string) =>
  declsFor(css, selector).find((decl) => decl.prop === prop)?.value;

const panel = (props: Partial<Parameters<typeof SidePanel>[0]> = {}) => (
  <SidePanel id="test" kind="filters" label="Filtrar colección" className="extra" {...props}>
    <p>Contenido del panel</p>
  </SidePanel>
);

afterEach(() => vi.restoreAllMocks());

describe('SidePanel (owner feedback S23)', () => {
  it('is a named region with a toggle that controls its content', async () => {
    await renderWithI18n(panel());
    const region = screen.getByRole('complementary', { name: 'Filtrar colección' });
    expect(region.className).toMatch(/extra/);
    expect(region).not.toHaveAttribute('data-collapsed');
    const toggle = screen.getByRole('button', { name: 'Ocultar filtros' });
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const content = document.getElementById(toggle.getAttribute('aria-controls')!);
    expect(content).toContainElement(screen.getByText('Contenido del panel'));
    expect(screen.getByText('Contenido del panel')).toBeVisible();
  });

  it('collapses on click: content hidden, the region stays, the choice is stored', async () => {
    await renderWithI18n(panel());
    await userEvent.click(screen.getByRole('button', { name: 'Ocultar filtros' }));
    const toggle = screen.getByRole('button', { name: 'Mostrar filtros' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    // still in the document, so aria-controls keeps pointing at it
    const content = document.getElementById(toggle.getAttribute('aria-controls')!)!;
    expect(content).toHaveAttribute('hidden');
    expect(screen.getByText('Contenido del panel')).not.toBeVisible();
    const region = screen.getByRole('complementary', { name: 'Filtrar colección' });
    expect(region).toHaveAttribute('data-collapsed');
    expect(localStorage.getItem('rb_panel_test_v1')).toBe('collapsed');

    await userEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Ocultar filtros' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    expect(screen.getByText('Contenido del panel')).toBeVisible();
    expect(localStorage.getItem('rb_panel_test_v1')).toBe('expanded');
  });

  it('opens collapsed when the panel was left collapsed, each panel on its own key', async () => {
    localStorage.setItem('rb_panel_test_v1', 'collapsed');
    await renderWithI18n(
      <>
        {panel()}
        <SidePanel id="other" kind="detail" label="Detalle de la carta" side="end">
          <p>Detalle</p>
        </SidePanel>
      </>,
    );
    expect(screen.getByRole('button', { name: 'Mostrar filtros' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(screen.getByRole('button', { name: 'Ocultar detalle' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('ignores unknown stored values and storage that throws', async () => {
    localStorage.setItem('rb_panel_test_v1', 'yes');
    const view = await renderWithI18n(panel());
    expect(screen.getByRole('button', { name: 'Ocultar filtros' })).toBeInTheDocument();
    view.unmount();

    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    await renderWithI18n(panel());
    await userEvent.click(screen.getByRole('button', { name: 'Ocultar filtros' }));
    expect(screen.getByRole('button', { name: 'Mostrar filtros' })).toBeInTheDocument();
  });

  it('names the toggle after the kind of panel, in both languages', async () => {
    const kinds = [
      ['filters', 'Ocultar filtros', 'Hide filters'],
      ['detail', 'Ocultar detalle', 'Hide details'],
      ['editor', 'Ocultar editor', 'Hide editor'],
      ['menu', 'Ocultar menú', 'Hide menu'],
      ['preview', 'Ocultar vista previa', 'Hide preview'],
    ] as const;
    for (const [kind, es, en] of kinds) {
      const spanish = await renderWithI18n(panel({ id: kind, kind }));
      expect(screen.getByRole('button', { name: es })).toBeInTheDocument();
      spanish.unmount();
      const english = await renderWithI18n(panel({ id: kind, kind }), 'en');
      expect(screen.getByRole('button', { name: en })).toBeInTheDocument();
      english.unmount();
    }
    const collapsed = await renderWithI18n(panel({ id: 'menu', kind: 'menu' }), 'en');
    await userEvent.click(screen.getByRole('button', { name: 'Hide menu' }));
    expect(screen.getByRole('button', { name: 'Show menu' })).toBeInTheDocument();
    collapsed.unmount();
  });

  it('passes attributes to the region and lays out the content with the caller class', async () => {
    await renderWithI18n(
      panel({ contentClassName: 'body', 'aria-busy': true, ...{ 'data-testid': 'filters' } }),
    );
    const region = screen.getByTestId('filters');
    expect(region).toBe(screen.getByRole('complementary', { name: 'Filtrar colección' }));
    expect(region).toHaveAttribute('aria-busy', 'true');
    const content = screen.getByText('Contenido del panel').parentElement!;
    expect(content.className).toMatch(/body/);
    expect(content.className).toMatch(/content/);
  });

  it('can be a navigation landmark (the admin menu)', async () => {
    await renderWithI18n(panel({ as: 'nav', label: 'Administración', kind: 'menu' }));
    expect(screen.getByRole('navigation', { name: 'Administración' })).toBeInTheDocument();
    expect(screen.queryByRole('complementary')).toBeNull();
  });

  it('has no axe violations open or collapsed', async () => {
    const { container } = await renderWithI18n(panel());
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Ocultar filtros' }));
    expect(await axe(container)).toHaveNoViolations();
  });

  it('collapsed, it shrinks to the toggle so the main column takes the width', () => {
    // two classes: outranks the width and padding the caller's class gives the panel
    expect(value('.root[data-collapsed]', 'width')).toBe('auto');
    expect(value('.root[data-collapsed]', 'padding')).toBeDefined();
    expect(value('.content[hidden]', 'display')).toBe('none');
  });

  it('keeps every rule in the components layer', () => {
    expect(rules(css).every((rule) => rule.atRules.includes('layer components'))).toBe(true);
  });
});
