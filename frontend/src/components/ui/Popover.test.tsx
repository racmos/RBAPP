import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { createI18n } from '@/i18n';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { Popover } from './Popover';

async function renderPopover() {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(
    <I18nextProvider i18n={i18n}>
      <main>
        <p>Outside</p>
        <Popover title="Filter cards" trigger={<>Filter</>} triggerLabel="Filter, 2 active">
          <button type="button">Inside</button>
        </Popover>
      </main>
    </I18nextProvider>,
  );
}

describe('Popover (F5-i step 3)', () => {
  it('the trigger opens a labelled panel and moves focus into it', async () => {
    await renderPopover();
    const trigger = screen.getByRole('button', { name: 'Filter, 2 active' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('dialog')).toBeNull();
    await userEvent.click(trigger);
    const panel = screen.getByRole('dialog', { name: 'Filter cards' });
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(trigger).toHaveAttribute('aria-controls', panel.id);
    expect(panel).toContainElement(document.activeElement as HTMLElement);
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('Escape closes it and focus goes back to the trigger', async () => {
    await renderPopover();
    const trigger = screen.getByRole('button', { name: 'Filter, 2 active' });
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole('button', { name: 'Inside' }));
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('the close button, the trigger and a click outside close it', async () => {
    await renderPopover();
    const trigger = screen.getByRole('button', { name: 'Filter, 2 active' });
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(trigger).toHaveFocus();

    await userEvent.click(trigger);
    await userEvent.click(trigger);
    expect(screen.queryByRole('dialog')).toBeNull();

    await userEvent.click(trigger);
    await userEvent.click(screen.getByText('Outside'));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('a function child gets a close that closes the panel and focuses the trigger', async () => {
    const i18n = await createI18n();
    const { I18nextProvider } = await import('react-i18next');
    render(
      <I18nextProvider i18n={i18n}>
        <Popover title="Deck actions" trigger={<>More</>} size="sm">
          {(close) => (
            <button type="button" onClick={close}>
              Run
            </button>
          )}
        </Popover>
      </I18nextProvider>,
    );
    const trigger = screen.getByRole('button', { name: 'More' });
    await userEvent.click(trigger);
    expect(screen.getByRole('dialog', { name: 'Deck actions' }).className).toMatch(/sm/);
    await userEvent.click(screen.getByRole('button', { name: 'Run' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it('a disabled trigger does not open', async () => {
    const i18n = await createI18n();
    const { I18nextProvider } = await import('react-i18next');
    render(
      <I18nextProvider i18n={i18n}>
        <Popover title="Deck actions" trigger={<>More</>} disabled>
          <p>Inside</p>
        </Popover>
      </I18nextProvider>,
    );
    const trigger = screen.getByRole('button', { name: 'More' });
    expect(trigger).toBeDisabled();
    await userEvent.click(trigger);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('the small panel is narrower, never wider than the screen', () => {
    const css = readCss(join(SRC_DIR, 'components/ui/Popover.module.css'));
    expect(declsFor(css, '.sm')).toContainEqual({
      prop: 'width',
      value: 'min(280px, calc(100vw - 2 * var(--pad)))',
    });
  });

  it('has an opaque panel, so the cards behind it never show through the text', () => {
    const css = readCss(join(SRC_DIR, 'components/ui/Popover.module.css'));
    const background = declsFor(css, '.panel').find((decl) => decl.prop === 'background')?.value;
    expect(background).toBe('var(--table-head)');
  });
});
