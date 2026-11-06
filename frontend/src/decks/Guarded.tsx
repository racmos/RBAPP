import { useId, type ReactNode } from 'react';
import { Button } from '@/components/ui/Button';

/** A control the rules may refuse: disabled, with the reason as tooltip and description. */
export function Guarded({
  label,
  reason,
  disabled,
  onClick,
  children,
}: {
  label: string;
  reason: string | null;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        aria-label={label}
        title={reason ?? label}
        disabled={disabled || reason !== null}
        aria-describedby={reason ? id : undefined}
        onClick={onClick}
      >
        {children}
      </Button>
      {reason && (
        <span id={id} className="sr-only">
          {reason}
        </span>
      )}
    </>
  );
}
