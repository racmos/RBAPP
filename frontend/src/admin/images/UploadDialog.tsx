import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import { fieldErrorsFromDetails } from '@/auth/formHelpers';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { translateError } from '@/i18n';
import { formatBytes } from '@/lib/format';
import { FormAlert } from '../FormAlert';
import { MAX_IMAGE_BYTES, isImageFile } from './matchFiles';
import { announceUpload, sendImage, type UploadResult, type UploadTarget } from './uploadImage';
import styles from './ImagesPage.module.css';

export type PickedImage = { target: UploadTarget; file: File };

/** The refusal of a field error on `file`, else the general text of the error. */
export function uploadErrorText(error: unknown, i18n: Parameters<typeof translateError>[1]) {
  if (error instanceof ApiError && error.kind === 'http' && error.status === 400) {
    const mapped = fieldErrorsFromDetails(error.details, i18n, ['file'] as const).file;
    if (mapped) return mapped;
  }
  return translateError(error, i18n);
}

/**
 * The preview of a picked image (F13-h S3): the picture, its name and size, then one upload on
 * Upload. A file the server would refuse for its type or size is refused here first.
 */
export function UploadDialog({
  picked,
  offline,
  onClose,
  onUploaded,
}: {
  picked: PickedImage | null;
  offline: boolean;
  onClose: () => void;
  onUploaded: (target: UploadTarget, result: UploadResult) => void;
}) {
  const { t } = useTranslation('admin');
  return (
    <Modal
      open={picked !== null}
      onClose={onClose}
      title={picked ? t('images.preview.title', { name: picked.target.name }) : ''}
    >
      {picked && (
        <Preview
          key={`${picked.target.name}:${picked.file.name}:${picked.file.lastModified}`}
          picked={picked}
          offline={offline}
          onClose={onClose}
          onUploaded={onUploaded}
        />
      )}
    </Modal>
  );
}

/** One picked file: its object URL lives as long as this body (a new pick remounts it). */
function Preview({
  picked,
  offline,
  onClose,
  onUploaded,
}: {
  picked: PickedImage;
  offline: boolean;
  onClose: () => void;
  onUploaded: (target: UploadTarget, result: UploadResult) => void;
}) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const { file, target } = picked;
  const refusal = !isImageFile(file)
    ? t('images.preview.notImage')
    : file.size > MAX_IMAGE_BYTES
      ? t('images.preview.tooLarge')
      : null;
  const [url] = useState(() => (refusal ? null : URL.createObjectURL(file)));
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );

  const upload = async () => {
    if (sending || refusal) return;
    setSending(true);
    setError(null);
    try {
      const result = await sendImage(target, file);
      onUploaded(target, result);
      announceUpload(i18n, queryClient, target, result);
      onClose();
    } catch (failure) {
      setError(uploadErrorText(failure, i18n));
      setSending(false);
    }
  };

  return (
    <div className={styles.preview}>
      {url && (
        <img
          className={styles.previewImage}
          src={url}
          alt={t('images.preview.alt', { file: file.name })}
        />
      )}
      <p>{t('images.preview.file', { file: file.name, size: formatBytes(file.size) })}</p>
      <p className={styles.hint}>
        {t(target.type === 'card' ? 'images.limits.cards' : 'images.limits.products')}
      </p>
      {refusal && <FormAlert message={refusal} />}
      {error && <FormAlert message={error} />}
      <div className={styles.previewActions}>
        <Button variant="ghost" onClick={onClose}>
          {common('actions.cancel')}
        </Button>
        <Button
          pending={sending}
          disabled={offline || refusal !== null}
          onClick={() => void upload()}
        >
          {t('images.preview.upload')}
        </Button>
      </div>
    </div>
  );
}
