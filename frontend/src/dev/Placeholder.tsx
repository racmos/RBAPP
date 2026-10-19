import { useId, useState } from 'react';
import { Brand } from '@/components/ui/Brand';
import { BG_DEFAULT_PERCENT, applyBackground } from '@/lib/background';

type PlaceholderProps = { showBackgroundSlider: boolean };

/** Temporary page of unit a: the brand over the background, plus a dev-only slider. */
export function Placeholder({ showBackgroundSlider }: PlaceholderProps) {
  const sliderId = useId();
  const [percent, setPercent] = useState(BG_DEFAULT_PERCENT);

  return (
    <main
      style={{
        display: 'grid',
        placeItems: 'center',
        gap: '2rem',
        minHeight: '100dvh',
        padding: 'var(--pad)',
      }}
    >
      <Brand variant="wordmark" />
      {showBackgroundSlider && (
        <div>
          <label htmlFor={sliderId}>Intensidad del fondo </label>
          <input
            id={sliderId}
            type="range"
            min={0}
            max={100}
            value={percent}
            onChange={(event) => {
              const next = Number(event.target.value);
              setPercent(next);
              applyBackground(document.documentElement, next);
            }}
          />
          <output htmlFor={sliderId}> {percent} %</output>
        </div>
      )}
    </main>
  );
}
