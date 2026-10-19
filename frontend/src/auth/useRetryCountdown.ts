import { useCallback, useEffect, useRef, useState } from 'react';

const TICK_MS = 250;

type Options = { onEnd?: () => void };

/**
 * A countdown in whole seconds (FAUTH-7). It follows the clock, not the number of ticks, so a
 * throttled background tab shows the right value when it wakes up.
 */
export function useRetryCountdown({ onEnd }: Options = {}) {
  const [remaining, setRemaining] = useState(0);
  const deadline = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const onEndRef = useRef(onEnd);
  useEffect(() => {
    onEndRef.current = onEnd;
  });

  const stop = useCallback(() => clearInterval(timer.current), []);

  const start = useCallback(
    (seconds: number) => {
      if (!Number.isFinite(seconds) || seconds <= 0) return;
      stop();
      deadline.current = Date.now() + seconds * 1000;
      setRemaining(seconds);
      timer.current = setInterval(() => {
        const left = Math.max(0, Math.ceil((deadline.current - Date.now()) / 1000));
        setRemaining(left);
        if (left === 0) {
          stop();
          onEndRef.current?.();
        }
      }, TICK_MS);
    },
    [stop],
  );

  useEffect(() => stop, [stop]);

  return { remaining, active: remaining > 0, start };
}
