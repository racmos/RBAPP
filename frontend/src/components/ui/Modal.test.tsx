import { fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithI18n } from '@/test/i18n';
import { ConfirmDialog } from './ConfirmDialog';
import { Modal } from './Modal';
import { Sheet } from './Sheet';

function ModalDemo({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Abrir</button>
      <Modal
        open={open}
        title="Detalle"
        onClose={() => {
          setOpen(false);
          onClose?.();
        }}
      >
        <button>Dentro</button>
      </Modal>
    </>
  );
}

const dialog = () => screen.getByRole('dialog', { name: 'Detalle' });

describe('Modal (DS-8, D17)', () => {
  it('is hidden until opened, then a modal dialog named by its title', async () => {
    await renderWithI18n(<ModalDemo />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    expect(dialog()).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Detalle' })).toBeVisible();
  });

  it('moves focus inside when it opens', async () => {
    await renderWithI18n(<ModalDemo />);
    await userEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    expect(dialog()).toContainElement(document.activeElement as HTMLElement);
  });

  it('Escape closes it and focus returns to the opener', async () => {
    const onClose = vi.fn();
    await renderWithI18n(<ModalDemo onClose={onClose} />);
    const opener = screen.getByRole('button', { name: 'Abrir' });
    await userEvent.click(opener);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('the close button closes it and returns focus', async () => {
    await renderWithI18n(<ModalDemo />);
    const opener = screen.getByRole('button', { name: 'Abrir' });
    await userEvent.click(opener);
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  describe('backdrop', () => {
    it('closes when pointerdown and pointerup both land on the dialog itself', async () => {
      await renderWithI18n(<ModalDemo />);
      await userEvent.click(screen.getByRole('button', { name: 'Abrir' }));
      await userEvent.click(dialog()); // a click on the backdrop targets the dialog element
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('does not close when the press started inside the content', async () => {
      await renderWithI18n(<ModalDemo />);
      await userEvent.click(screen.getByRole('button', { name: 'Abrir' }));
      fireEvent.pointerDown(screen.getByRole('button', { name: 'Dentro' }));
      fireEvent.pointerUp(dialog());
      expect(dialog()).toBeVisible();
    });

    it('does not close when the press ends inside the content', async () => {
      await renderWithI18n(<ModalDemo />);
      await userEvent.click(screen.getByRole('button', { name: 'Abrir' }));
      fireEvent.pointerDown(dialog());
      fireEvent.pointerUp(screen.getByRole('button', { name: 'Dentro' }));
      expect(dialog()).toBeVisible();
    });

    it('does not close when a click lands on the content', async () => {
      await renderWithI18n(<ModalDemo />);
      await userEvent.click(screen.getByRole('button', { name: 'Abrir' }));
      await userEvent.click(screen.getByRole('button', { name: 'Dentro' }));
      expect(dialog()).toBeVisible();
    });
  });

  it('can be closed from the parent state alone', async () => {
    function Controlled() {
      const [open, setOpen] = useState(true);
      return (
        <>
          <Modal open={open} title="Detalle" onClose={() => setOpen(false)}>
            x
          </Modal>
          <button onClick={() => setOpen(false)}>Cerrar desde fuera</button>
        </>
      );
    }
    await renderWithI18n(<Controlled />);
    expect(dialog()).toBeVisible();
    // The dialog is modal in a browser; here the outside button is reachable on purpose.
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar desde fuera' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('Sheet (DS-8)', () => {
  it('is a dialog that closes like a Modal', async () => {
    function SheetDemo() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Más</button>
          <Sheet open={open} title="Más opciones" onClose={() => setOpen(false)}>
            contenido
          </Sheet>
        </>
      );
    }
    await renderWithI18n(<SheetDemo />);
    const opener = screen.getByRole('button', { name: 'Más' });
    await userEvent.click(opener);
    expect(screen.getByRole('dialog', { name: 'Más opciones' })).toBeVisible();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});

describe('ConfirmDialog (DS-8)', () => {
  const setup = async (props: { onConfirm?: () => void; onCancel?: () => void } = {}) => {
    const onConfirm = props.onConfirm ?? vi.fn();
    const onCancel = props.onCancel ?? vi.fn();
    await renderWithI18n(
      <ConfirmDialog
        open
        title="¿Borrar mazo?"
        message="No se puede deshacer."
        confirmLabel="Borrar"
        cancelLabel="Cancelar"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    return { onConfirm, onCancel };
  };

  it('asks, with the message, and focuses the safe choice', async () => {
    await setup();
    expect(screen.getByRole('dialog', { name: '¿Borrar mazo?' })).toBeVisible();
    expect(screen.getByText('No se puede deshacer.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus();
  });

  it('confirms and cancels through its buttons', async () => {
    const { onConfirm, onCancel } = await setup();
    await userEvent.click(screen.getByRole('button', { name: 'Borrar' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('Escape cancels', async () => {
    const { onConfirm, onCancel } = await setup();
    await userEvent.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('a click on the backdrop does NOT close it', async () => {
    const { onCancel } = await setup();
    await userEvent.click(screen.getByRole('dialog'));
    expect(onCancel).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeVisible();
  });
});
