import { fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRef, useState } from 'react';
import { describe, expect, it } from 'vitest';
import { renderWithI18n } from '@/test/i18n';
import { Modal } from './Modal';

describe('Modal returnFocusRef', () => {
  it('returns focus to the given element even when the opener did not keep focus', async () => {
    function Demo() {
      const [open, setOpen] = useState(false);
      const ref = useRef<HTMLButtonElement>(null);
      return (
        <>
          <button ref={ref} onClick={() => setOpen(true)}>
            Abrir
          </button>
          <Modal open={open} title="Detalle" onClose={() => setOpen(false)} returnFocusRef={ref}>
            x
          </Modal>
        </>
      );
    }
    await renderWithI18n(<Demo />);
    const opener = screen.getByRole('button', { name: 'Abrir' });
    // Safari does not focus a button on click: opening leaves body as the active element.
    fireEvent.click(opener);
    expect(opener).not.toHaveFocus();
    await userEvent.keyboard('{Escape}');
    expect(opener).toHaveFocus();
  });
});
