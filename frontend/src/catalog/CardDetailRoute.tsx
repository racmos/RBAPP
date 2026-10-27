import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
  useSearchParams,
} from 'react-router';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Modal } from '@/components/ui/Modal';
import { useCardDetail } from './queries';
import type { CardDetailOutletContext } from './context';
import { CardDetailView } from './CardDetailView';
import styles from './CardDetailRoute.module.css';

export function CardDetailRoute() {
  const { t } = useTranslation(['cards', 'common']);
  const { setId, cardId } = useParams<{ setId: string; cardId: string }>();
  const context = useOutletContext<CardDetailOutletContext>();
  const presentation = context?.presentation ?? 'page';
  const siblings = context?.siblings;
  const onClose = context?.onClose;
  const query = useCardDetail(setId, cardId);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const titleRef = useRef<HTMLHeadingElement>(null);

  const currentIndex = useMemo(() => {
    if (!siblings || !setId || !cardId) return -1;
    return siblings.findIndex((s) => s.setId === setId && s.cardId === cardId);
  }, [siblings, setId, cardId]);

  const canPrev = currentIndex > 0;
  const canNext = currentIndex !== -1 && currentIndex < (siblings?.length ?? 0) - 1;

  const goTo = useCallback(
    (index: number) => {
      if (!siblings) return;
      const target = siblings[index];
      if (!target) return;
      void navigate(
        {
          pathname: `../${target.setId}/${target.cardId}`,
          search: searchParams.toString(),
        },
        { replace: true, state: location.state },
      );
    },
    [siblings, navigate, searchParams, location.state],
  );

  useEffect(() => {
    if (presentation !== 'modal') return;
    const handler = (event: KeyboardEvent) => {
      const active = document.activeElement;
      const typing =
        active instanceof HTMLInputElement ||
        active instanceof HTMLTextAreaElement ||
        active instanceof HTMLSelectElement;
      if (typing) return;
      if (event.key === 'ArrowLeft' && canPrev) {
        event.preventDefault();
        goTo(currentIndex - 1);
      } else if (event.key === 'ArrowRight' && canNext) {
        event.preventDefault();
        goTo(currentIndex + 1);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [presentation, canPrev, canNext, currentIndex, goTo]);

  useEffect(() => {
    if (query.data && titleRef.current) {
      titleRef.current.focus();
    }
  }, [query.data]);

  const view = (
    <CardDetailView
      presentation={presentation}
      card={query.data}
      isPending={query.isPending}
      isError={query.isError}
      error={(query.error as Error | null) ?? null}
      onRetry={() => query.refetch()}
    />
  );

  if (presentation === 'modal') {
    return (
      <Modal
        open
        onClose={onClose ?? (() => {})}
        title={query.data?.name ?? ''}
        size="xl"
        hideTitle
      >
        <div className={styles.modalInner}>
          {siblings && siblings.length > 0 && (
            <div className={styles.nav}>
              <Button
                variant="ghost"
                size="sm"
                disabled={!canPrev}
                onClick={() => goTo(currentIndex - 1)}
                aria-label={t('detail.nav.prev')}
              >
                <Icon name="arrow" size={16} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!canNext}
                onClick={() => goTo(currentIndex + 1)}
                aria-label={t('detail.nav.next')}
              >
                <Icon name="arrow" size={16} className={styles.nextIcon} />
              </Button>
            </div>
          )}
          {view}
        </div>
      </Modal>
    );
  }

  // page presentation
  const handleBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      void navigate('/cards');
    }
  };

  return (
    <div className={styles.page}>
      <Button variant="ghost" size="sm" onClick={handleBack} className={styles.back}>
        <Icon name="arrow" size={16} className={styles.backIcon} />
        {t('common:actions.back')}
      </Button>
      {view}
    </div>
  );
}
