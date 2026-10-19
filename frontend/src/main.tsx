// The stylesheet comes first: it declares the @layer order (D15), and CSS reaches the page in
// import order, so a component module imported earlier would fix a different order.
import '@/styles/index.css';
import { startApp } from '@/app/bootstrap';

void startApp(document.getElementById('root')!);
