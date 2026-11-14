/**
 * The account sections (F9-i S2), in screen order: one list behind the tabs and the sidebar.
 * F9-j adds `security` and `api` between them (Profile, Security, API, Interface).
 */
export type AccountSectionId = 'profile' | 'interface';
export type AccountSection = {
  id: AccountSectionId;
  /** Router path, without the basename. */ to: string;
};

export const ACCOUNT_SECTIONS: readonly AccountSection[] = [
  { id: 'profile', to: '/account/profile' },
  { id: 'interface', to: '/account/interface' },
];
