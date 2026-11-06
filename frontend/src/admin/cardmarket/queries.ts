import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  getCardmarketLoad,
  getCardmarketStatus,
  listAdminJobs,
  listCardmarketLoads,
} from '@/api/endpoints';
import { isActiveJob } from './format';

/** Query keys of the Cardmarket screen; every one lives under `['admin']` (F13-f S1). */
export const cardmarketKeys = {
  all: ['admin', 'cardmarket'] as const,
  status: ['admin', 'cardmarket', 'status'] as const,
  loads: (limit: number) => ['admin', 'cardmarket', 'loads', limit] as const,
  day: (date: string) => ['admin', 'cardmarket', 'day', date] as const,
  jobs: ['admin', 'jobs', { kind: 'daily_prices' }] as const,
};

export const POLL_MS = 3000;
export const RECENT_JOBS = 10;

/** The header data; polled every 3 s while the latest job is queued or running. */
export const useCardmarketStatus = () =>
  useQuery({
    queryKey: cardmarketKeys.status,
    queryFn: ({ signal }) => getCardmarketStatus(signal),
    refetchInterval: (query) => (isActiveJob(query.state.data?.job?.status) ? POLL_MS : false),
  });

export const useCardmarketLoads = (limit: number) =>
  useQuery({
    queryKey: cardmarketKeys.loads(limit),
    queryFn: ({ signal }) => listCardmarketLoads(limit, signal),
    // Keep the rows on screen while "Show more" loads the longer list.
    placeholderData: keepPreviousData,
  });

export const useCardmarketDay = (date: string) =>
  useQuery({
    queryKey: cardmarketKeys.day(date),
    queryFn: ({ signal }) => getCardmarketLoad(date, signal),
  });

/** The last `daily_prices` runs: a failed load leaves no history row, only its job. */
export const useCardmarketJobs = () =>
  useQuery({
    queryKey: cardmarketKeys.jobs,
    queryFn: ({ signal }) => listAdminJobs({ kind: 'daily_prices', limit: RECENT_JOBS }, signal),
  });
