import { useContext } from 'react';
import { PrefsContext, type PrefsApi } from './context';

export function usePrefs(): PrefsApi {
  const api = useContext(PrefsContext);
  if (!api) throw new Error('usePrefs must be used under <PrefsProvider>');
  return api;
}
