import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/** One MSW server for all jsdom tests; `setup.ts` starts it with `onUnhandledFrame: 'error'`. */
export const server = setupServer(...handlers);
