import { join } from 'node:path';
import { useState } from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { createI18n } from '@/i18n';
import { Modal } from './Modal';
import styles from './Modal.module.css';

async function renderModal(
  props: Omit<React.ComponentProps<typeof Modal>, 'open' | 'onClose' | 'title' | 'children'>,
) {
  const i18n = await createI18n();
  const { I18nextProvider } = await import('react-i18next');
  return render(
    <I18nextProvider i18n={i18n}>
      <Modal open title="Test modal" onClose={() => {}} {...props}>
        Content
      </Modal>
    </I18nextProvider>,
  );
}

describe('Modal (F2-f S10)', () => {
  it('uses the md width by default', async () => {
    await renderModal({});
    const dialog = document.querySelector('dialog');
    expect(dialog).toHaveClass(styles.modal);
    expect(dialog).not.toHaveClass(styles.lg);
    expect(dialog).not.toHaveClass(styles.xl);
  });

  it('adds the lg class when size is lg', async () => {
    await renderModal({ size: 'lg' });
    expect(document.querySelector('dialog')).toHaveClass(styles.lg);
  });

  it('adds the xl class when size is xl', async () => {
    await renderModal({ size: 'xl' });
    expect(document.querySelector('dialog')).toHaveClass(styles.xl);
  });

  it('still renders the title and content', async () => {
    await renderModal({ size: 'xl' });
    expect(screen.getByRole('heading', { name: 'Test modal' })).toBeVisible();
    expect(screen.getByText('Content')).toBeVisible();
  });
});

/** A sheet with a button that opens a second modal over it (a card zoom in the card browser). */
function Nested() {
  const [outer, setOuter] = useState(true);
  const [inner, setInner] = useState(false);
  return (
    <>
      <p>{outer ? 'outer open' : 'outer closed'}</p>
      <Modal open={outer} title="Outer" onClose={() => setOuter(false)}>
        <button type="button" onClick={() => setInner(true)}>
          Open inner
        </button>
        <Modal open={inner} title="Inner" onClose={() => setInner(false)}>
          Inner content
        </Modal>
      </Modal>
    </>
  );
}

describe('Modal over a modal', () => {
  async function renderNested() {
    const i18n = await createI18n();
    const { I18nextProvider } = await import('react-i18next');
    render(
      <I18nextProvider i18n={i18n}>
        <Nested />
      </I18nextProvider>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Open inner' }));
    return screen.getByRole('dialog', { name: 'Inner' });
  }

  it('Escape closes only the top one, and focus goes back to its opener', async () => {
    const inner = await renderNested();
    await userEvent.keyboard('{Escape}');
    expect(inner).not.toHaveAttribute('open');
    expect(screen.getByRole('dialog', { name: 'Outer' })).toHaveAttribute('open');
    expect(screen.getByText('outer open')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open inner' })).toHaveFocus();
  });

  it('its close button closes only the top one', async () => {
    const inner = await renderNested();
    await userEvent.click(within(inner).getByRole('button', { name: 'Close' }));
    expect(inner).not.toHaveAttribute('open');
    expect(screen.getByText('outer open')).toBeInTheDocument();
  });
});

describe('Modal surface (owner feedback S24 o)', () => {
  const css = readCss(join(SRC_DIR, 'components/ui/Modal.module.css'));
  const last = (selector: string, prop: string) =>
    declsFor(css, selector).findLast((decl) => decl.prop === prop)?.value;

  it('is opaque: the page behind a sheet or a dialog never shows through', () => {
    // the panel tone over an opaque base, like the combobox popup
    expect(last('.surface', 'background-color')).toBe('var(--bg-0)');
    expect(last('.surface', 'background-image')).toBe(
      'linear-gradient(var(--panel-3), var(--panel-3))',
    );
    expect(declsFor(css, '.surface').some((decl) => decl.prop === 'background')).toBe(false);
  });

  it('keeps the backdrop dim and translucent', () => {
    expect(last('.dialog::backdrop', 'background')).toBe('rgba(3, 14, 19, 0.72)');
  });
});
