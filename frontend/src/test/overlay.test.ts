import { describe, expect, it } from 'vitest';
import type { Overlay } from '@/lib/background';
import { overlayOver } from './overlay';

const WHITE = [255, 255, 255] as const;
const at = (x: number, y: number) => ({ x, y, width: 100, height: 200 });

describe('overlayOver', () => {
  const linear: Overlay = {
    kind: 'linear',
    stops: [
      { color: [0, 0, 0, 0], at: 0 },
      { color: [0, 0, 0, 1], at: 1 },
    ],
  };

  it('interpolates a linear overlay top to bottom', () => {
    expect(overlayOver(WHITE, [linear], at(50, 0))).toEqual([255, 255, 255]);
    expect(overlayOver(WHITE, [linear], at(50, 100))[0]).toBeCloseTo(127.5, 5);
    expect(overlayOver(WHITE, [linear], at(50, 200))).toEqual([0, 0, 0]);
  });

  it('measures a radial overlay from its centre, scaled by its radii', () => {
    const radial: Overlay = {
      kind: 'radial',
      radius: [0.5, 0.5],
      center: [0.5, 0.5],
      stops: [
        { color: [0, 0, 0, 1], at: 0 },
        { color: [0, 0, 0, 0], at: 1 },
      ],
    };
    expect(overlayOver(WHITE, [radial], at(50, 100))).toEqual([0, 0, 0]); // centre
    expect(overlayOver(WHITE, [radial], at(75, 100))[0]).toBeCloseTo(127.5, 5); // half a radius
    expect(overlayOver(WHITE, [radial], at(100, 100))).toEqual([255, 255, 255]); // on the edge
  });

  it('paints the first overlay on top', () => {
    const red: Overlay = { kind: 'linear', stops: [{ color: [255, 0, 0, 1], at: 0 }] };
    const blue: Overlay = { kind: 'linear', stops: [{ color: [0, 0, 255, 1], at: 0 }] };
    expect(overlayOver(WHITE, [red, blue], at(0, 0))).toEqual([255, 0, 0]);
    expect(overlayOver(WHITE, [blue, red], at(0, 0))).toEqual([0, 0, 255]);
  });
});
