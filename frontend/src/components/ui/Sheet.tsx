import { Modal, type ModalProps } from './Modal';

/** A modal anchored to the bottom edge: the phone's "Más" menu and similar (SHELL-4). */
export function Sheet(props: Omit<ModalProps, 'variant'>) {
  return <Modal {...props} variant="sheet" />;
}
