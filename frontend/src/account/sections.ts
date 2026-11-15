/**
 * The account sections (F9-i S2), in screen order: one list behind the tabs and the sidebar.
 * F9-j S1: Profile, Security, API, Interface.
 */
export type AccountSectionId = 'profile' | 'security' | 'api' | 'interface';
export type AccountSection = {
  id: AccountSectionId;
  /** Router path, without the basename. */ to: string;
};

export const ACCOUNT_SECTIONS: readonly AccountSection[] = [
  { id: 'profile', to: '/account/profile' },
  { id: 'security', to: '/account/security' },
  { id: 'api', to: '/account/api' },
  { id: 'interface', to: '/account/interface' },
];
