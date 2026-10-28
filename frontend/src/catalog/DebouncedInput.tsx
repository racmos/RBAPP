import { useCallback, useEffect, useRef, useState, type ComponentProps } from 'react';
import { Input } from '@/components/ui/Input';

const DEFAULT_DELAY_MS = 300;

type DebouncedInputProps = Omit<ComponentProps<typeof Input>, 'value' | 'onChange'> & {
  /** What the URL says now. */
  value: string;
  /** Called with the typed text after `delay` ms without typing, or at once on Enter. */
  onCommit: (next: string) => void;
  delay?: number;
};

/**
 * A text input whose value lives in the URL. It keeps what the user types in local state and
 * only adopts `value` when it did not come from this input: the URL answers a commit some time
 * later, and writing that answer back would erase the letters typed in the meantime.
 */
export function DebouncedInput({
  value,
  onCommit,
  delay = DEFAULT_DELAY_MS,
  onKeyDown,
  ...rest
}: DebouncedInputProps) {
  const [local, setLocal] = useState(value);
  const sent = useRef(new Set<string>()); // committed, answer from the URL not seen yet
  const commitRef = useRef(onCommit);
  useEffect(() => {
    commitRef.current = onCommit;
  });

  const send = useCallback((next: string) => {
    sent.current.add(next);
    commitRef.current(next);
  }, []);

  useEffect(() => {
    if (sent.current.delete(value)) return;
    sent.current.clear();
    setLocal(value);
  }, [value]);

  useEffect(() => {
    if (local === value) return;
    const timer = setTimeout(() => send(local), delay);
    return () => clearTimeout(timer);
  }, [local, value, delay, send]);

  return (
    <Input
      {...rest}
      value={local}
      onChange={(event) => setLocal(event.target.value)}
      onKeyDown={(event) => {
        onKeyDown?.(event);
        if (event.key === 'Enter' && local !== value) send(local);
      }}
    />
  );
}
