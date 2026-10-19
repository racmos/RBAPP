// The stylesheet comes first: it declares the @layer order (D15), and CSS reaches the page in
// import order, so a component module imported earlier would fix a different order.
import '@/styles/index.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Placeholder } from '@/dev/Placeholder';
import { BG_DEFAULT_PERCENT, applyBackground } from '@/lib/background';

applyBackground(document.documentElement, BG_DEFAULT_PERCENT);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Placeholder showBackgroundSlider={import.meta.env.DEV} />
  </StrictMode>,
);
