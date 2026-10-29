import {
  useCallback,
  useEffect,
  useRef,
  type ComponentProps,
  type ReactNode,
  type Ref,
} from 'react';
import { Icon } from './Icon';
import styles from './Checkbox.module.css';

type CheckboxProps = Omit<ComponentProps<'input'>, 'type'> & {
  label: ReactNode;
  /** Keeps the label as the accessible name only (table selection boxes). */
  hideLabel?: boolean;
  /** The mixed state of a "select all" box. */
  indeterminate?: boolean;
};

function assignRef<T>(ref: Ref<T> | undefined, value: T | null) {
  if (typeof ref === 'function') ref(value);
  else if (ref) ref.current = value;
}

/**
 * A toggle button that lights up when checked. Underneath it is a native checkbox stretched
 * over the button and made transparent, so clicks, Space, focus and screen readers keep the
 * browser's checkbox behaviour; the check mark is the non-colour cue of the checked state.
 */
export function Checkbox({
  label,
  hideLabel,
  indeterminate = false,
  className,
  ref,
  ...rest
}: CheckboxProps) {
  const inner = useRef<HTMLInputElement | null>(null);
  const setRef = useCallback(
    (node: HTMLInputElement | null) => {
      inner.current = node;
      assignRef(ref, node);
    },
    [ref],
  );
  useEffect(() => {
    if (inner.current) inner.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <label
      className={[styles.checkbox, className].filter(Boolean).join(' ')}
      data-icon-only={hideLabel || undefined}
    >
      <input ref={setRef} type="checkbox" className={styles.input} {...rest} />
      <span className={styles.face}>
        <span className={styles.tick} data-slot="checkbox-tick" aria-hidden="true">
          <Icon name={indeterminate ? 'minus' : 'check'} size={14} />
        </span>
        <span className={hideLabel ? 'sr-only' : styles.text}>{label}</span>
      </span>
    </label>
  );
}
