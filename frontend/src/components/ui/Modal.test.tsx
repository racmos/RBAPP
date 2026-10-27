import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { createI18n } from '@/i18n';
import { Modal } from './Modal';
import styles from './Modal.module.css';

async function renderModal(
  props: Omit<React.ComponentProps<typeof Modal>, 'open' | 'onClose' | 'title' | 'children'>,
) {
  const i18n = await createI18n('es');
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
