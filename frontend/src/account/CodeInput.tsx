import { Input, type InputProps } from '@/components/ui/Input';
import styles from './SecurityPage.module.css';

/** A 6-digit authenticator code (F9-j S3): numeric keypad, one-time-code autofill. */
export function CodeInput({ className, ...rest }: Omit<InputProps, 'type'>) {
  return (
    <Input
      {...rest}
      type="text"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      spellCheck={false}
      className={[styles.code, className].filter(Boolean).join(' ')}
    />
  );
}
