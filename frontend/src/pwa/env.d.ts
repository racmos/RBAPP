/// <reference types="vite-plugin-pwa/react" />

interface ImportMetaEnv {
  /** "true" for the rollback build: the worker unregisters itself and the app must not register one (PWA-5). */
  readonly VITE_PWA_SELF_DESTROY?: string;
}
