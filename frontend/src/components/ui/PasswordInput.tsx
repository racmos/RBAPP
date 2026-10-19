import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from './Icon';
import { Input, type InputProps } from './Input';
import styles from './PasswordInput.module.css';

/** A password field with a show/hide control that has an accessible name (FAUTH-10). */
export function PasswordInput({ className, ...rest }: Omit<InputProps, 'type'>) {
  const { t } = useTranslation('common');
  const [visible, setVisible] = useState(false);
  const label = visible ? t('password.hide') : t('password.show');

  return (
    <span className={styles.wrap}>
      <Input
        {...rest}
        type={visible ? 'text' : 'password'}
        className={[styles.input, className].filter(Boolean).join(' ')}
      />
      <button
        type="button"
        className={styles.toggle}
        aria-label={label}
        onClick={() => setVisible(!visible)}
      >
        <Icon name={visible ? 'eye-off' : 'eye'} />
      </button>
    </span>
  );
}
