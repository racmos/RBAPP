import { useEffect, useState } from 'react';
import type { CardSummary } from '@/api/types';
import { CardArtPlaceholder } from './CardArtPlaceholder';
import styles from './CardImage.module.css';

type CardImageCard = Pick<
  CardSummary,
  'name' | 'image_src' | 'image_thumb_src' | 'domains' | 'type' | 'supertype' | 'energy' | 'might'
>;

type CardImageProps = {
  card: CardImageCard;
  size: 'thumb' | 'tile' | 'full';
  decorative?: boolean;
  priority?: boolean;
  className?: string;
};

type LoadState =
  { kind: 'initial'; src: string } | { kind: 'full'; src: string } | { kind: 'placeholder' };

function initialState(card: CardImageCard, size: CardImageProps['size']): LoadState {
  const fullSrc = card.image_src;
  const thumbSrc = card.image_thumb_src ?? fullSrc;
  const src = size === 'full' ? fullSrc : thumbSrc;
  return src ? { kind: 'initial', src } : { kind: 'placeholder' };
}

export function CardImage({ card, size, decorative, priority, className }: CardImageProps) {
  const [state, setState] = useState<LoadState>(() => initialState(card, size));

  // Reset the load state when the image identity changes.
  /* eslint-disable react-hooks/set-state-in-effect -- derived reset on prop change */
  useEffect(() => {
    setState(initialState(card, size));
  }, [card, size]);
  /* eslint-enable react-hooks/set-state-in-effect */

  if (state.kind === 'placeholder') {
    return (
      <CardArtPlaceholder
        card={card}
        decorative={decorative}
        className={[styles.box, className].filter(Boolean).join(' ')}
      />
    );
  }

  const handleError = () => {
    if (state.kind === 'initial' && card.image_src && state.src !== card.image_src) {
      setState({ kind: 'full', src: card.image_src });
    } else {
      setState({ kind: 'placeholder' });
    }
  };

  return (
    <div className={[styles.box, className].filter(Boolean).join(' ')}>
      <img
        src={state.src}
        alt={decorative ? '' : card.name}
        width={352}
        height={492}
        decoding="async"
        loading={priority ? 'eager' : 'lazy'}
        className={styles.image}
        onError={handleError}
      />
    </div>
  );
}
