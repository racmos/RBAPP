import { Button } from './Button';
import styles from './ConfirmDialog.module.css';
import { Modal } from './Modal';

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  /** The action destroys something: the confirm button is red. */
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/** Ask before something irreversible. Escape and the Cancel button cancel; the backdrop does not. */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} title={title} onClose={onCancel} dismissOnBackdrop={false} hideClose>
      <p className={styles.message}>{message}</p>
      <div className={styles.actions}>
        <Button variant="ghost" data-autofocus onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
