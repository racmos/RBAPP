import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { useSession } from '@/auth';
import { Avatar } from '@/components/ui/Avatar';
import { Icon } from '@/components/ui/Icon';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel } from '@/components/ui/Panel';
import { useDocumentTitle } from '@/i18n';
import styles from './HomeHub.module.css';
import { NavItem } from './NavItem';
import { navEntries } from './navRegistry';

/**
 * The SPA home (SHELL-6): a launcher into the modules. Each tile follows its registry status, so
 * a module that is still a Jinja page opens as a full navigation until its phase ports it.
 */
export function HomeHub() {
  const { t } = useTranslation('nav');
  const session = useSession();
  const username = session?.user?.username ?? '';
  const entries = navEntries('hub', { isAdmin: session?.user?.is_admin === true });
  useDocumentTitle(t('items.home.label'));

  return (
    <>
      <PageHeader title={t('welcome', { username })} subtitle={t('hub.subtitle')} />
      <div className={styles.layout}>
        <ul className={styles.grid}>
          {entries.map((entry) => (
            <li key={entry.id}>
              <NavItem entry={entry} className={styles.card}>
                <Icon name={entry.icon} size={24} className={styles.icon} />
                <span className={styles.text}>
                  <span className={styles.title} data-launcher-title>
                    {t(`items.${entry.id}.label`)}
                  </span>
                  <span className={styles.description}>{t(`items.${entry.id}.description`)}</span>
                </span>
                {entry.status === 'legacy' && (
                  <span className={styles.classic}>
                    <Icon name="external-link" size={14} />
                    <span className="sr-only">{t('hub.classic')}</span>
                  </span>
                )}
              </NavItem>
            </li>
          ))}
        </ul>

        <aside className={styles.side}>
          <Panel title={t('hub.account')}>
            <div className={styles.who}>
              <Avatar name={username} size={44} />
              <div>
                <p className={styles.username}>{username}</p>
                <p className={styles.email}>{session?.user?.email}</p>
              </div>
            </div>
            <Link to="/account/interface" className={styles.customize}>
              <Icon name="sliders" size={18} />
              <span>
                <span className={styles.title}>{t('hub.customize')}</span>
                <span className={styles.description}>{t('hub.customizeHint')}</span>
              </span>
            </Link>
          </Panel>
        </aside>
      </div>
    </>
  );
}
