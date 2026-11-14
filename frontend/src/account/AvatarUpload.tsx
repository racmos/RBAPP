import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { deleteAvatar, uploadAvatar } from '@/api/endpoints';
import { FormAlert } from '@/auth/FormAlert';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Modal } from '@/components/ui/Modal';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import styles from './ProfilePage.module.css';
import { applyUserChange } from './queries';

/** The formats the server decodes (F9-c S3) and its size limit. */
const ACCEPT = 'image/jpeg,image/png,image/webp,image/gif';
const MAX_MB = 5;
const MAX_BYTES = MAX_MB * 1024 * 1024;

type Preview = { file: File; url: string };

/**
 * "Change photo" and "Remove photo" of the identity card (F9-i S5, S6). A chosen file is checked
 * for size in the browser, then previewed in a circle with the same centre crop the server makes;
 * only "Use this photo" uploads it.
 */
export function AvatarUpload({
  hasPhoto,
  name,
  offline,
}: {
  hasPhoto: boolean;
  /** The name of the photo's owner, for the preview's text alternative. */
  name: string;
  offline: boolean;
}) {
  const { t, i18n } = useTranslation('account');
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const changeButton = useRef<HTMLButtonElement>(null);
  const [pickError, setPickError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removing, setRemoving] = useState(false);

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = ''; // the same file can be chosen again
    setPickError(null);
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setPickError(i18n.t('errors:code.file_too_large', { max_mb: MAX_MB }));
      return;
    }
    setUploadError(null);
    setPreview({ file, url: URL.createObjectURL(file) });
  };

  const closePreview = () => {
    setPreview((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
    setUploadError(null);
  };

  const uploadPhoto = async () => {
    if (!preview || uploading) return;
    setUploading(true);
    setUploadError(null);
    try {
      const { avatar_url } = await uploadAvatar(preview.file);
      applyUserChange(queryClient, { avatar_url }, { avatar_url });
      closePreview();
      pushToast({ kind: 'success', message: t('photo.updated') });
    } catch (error) {
      setUploadError(translateError(error, i18n));
    } finally {
      setUploading(false);
    }
  };

  const remove = async () => {
    setConfirmRemove(false);
    setRemoving(true);
    try {
      await deleteAvatar();
      applyUserChange(queryClient, { avatar_url: null }, { avatar_url: null });
      pushToast({ kind: 'success', message: t('photo.removed') });
    } catch (error) {
      pushToast({ kind: 'error', message: translateError(error, i18n) });
    } finally {
      setRemoving(false);
    }
  };

  return (
    <div className={styles.photo}>
      <div className={styles.photoActions}>
        <Button
          ref={changeButton}
          variant="ghost"
          disabled={offline}
          onClick={() => input.current?.click()}
        >
          {t('identity.changePhoto')}
        </Button>
        {hasPhoto && (
          <Button
            variant="ghost"
            pending={removing}
            disabled={offline}
            onClick={() => setConfirmRemove(true)}
          >
            {t('identity.removePhoto')}
          </Button>
        )}
      </div>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        hidden
        tabIndex={-1}
        disabled={offline}
        onChange={onPick}
      />
      <p className={styles.hint}>{t('identity.photoHint')}</p>
      {pickError && (
        <p role="alert" className={styles.error}>
          {pickError}
        </p>
      )}

      <Modal
        open={preview !== null}
        onClose={closePreview}
        title={t('photo.title')}
        returnFocusRef={changeButton}
      >
        {preview && (
          <div className={styles.preview}>
            <img
              className={styles.previewImage}
              src={preview.url}
              alt={t('identity.photoAlt', { name })}
              width={160}
              height={160}
            />
            {uploadError && <FormAlert message={uploadError} />}
            <div className={styles.previewActions}>
              <Button variant="ghost" onClick={closePreview}>
                {t('photo.cancel')}
              </Button>
              <Button pending={uploading} onClick={() => void uploadPhoto()}>
                {uploading ? t('photo.uploading') : t('photo.use')}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={confirmRemove}
        title={t('photo.removeTitle')}
        message={t('photo.removeBody')}
        confirmLabel={t('photo.removeConfirm')}
        cancelLabel={t('photo.cancel')}
        danger
        onConfirm={() => void remove()}
        onCancel={() => setConfirmRemove(false)}
      />
    </div>
  );
}
