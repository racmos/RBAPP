import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  addMyProduct,
  deleteMyProduct,
  getProduct,
  getProductPrices,
  listMyProducts,
  listProducts,
  patchMyProduct,
  type PriceRange,
} from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import type { MyProductAddBody, MyProductPatchBody, ProductListParams } from '@/api/types';
import { serializeProductParams } from './params';

const STALE_MS = 60 * 1000;

/** The catalog list for the URL params (F14-e S2). */
export function useProductList(params: ProductListParams) {
  const query = serializeProductParams(params);
  return useQuery({
    queryKey: ['products', 'list', query] as const,
    queryFn: ({ signal }) => listProducts(query, signal),
    placeholderData: keepPreviousData,
    staleTime: STALE_MS,
  });
}

const notFound = (error: unknown) => error instanceof ApiError && error.status === 404;

export function useProduct(id: number) {
  return useQuery({
    queryKey: ['products', 'detail', id] as const,
    queryFn: ({ signal }) => getProduct(id, signal),
    staleTime: STALE_MS,
    retry: (count, error) => !notFound(error) && count < 1,
    enabled: Number.isInteger(id) && id > 0,
  });
}

export function useProductPrices(id: number, range: PriceRange) {
  return useQuery({
    queryKey: ['products', 'prices', id, range] as const,
    queryFn: ({ signal }) => getProductPrices(id, range, signal),
    placeholderData: keepPreviousData,
    staleTime: 5 * STALE_MS,
    retry: false,
  });
}

/** The caller's owned lines and their total (F14-c). */
export function useMyProducts() {
  return useQuery({
    queryKey: ['me-products'] as const,
    queryFn: ({ signal }) => listMyProducts(signal),
    staleTime: STALE_MS,
  });
}

/** A write changes the owned lines and the `owned_qty` of the catalog, so it refreshes both. */
function useRefresh() {
  const client = useQueryClient();
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['me-products'] }),
      client.invalidateQueries({ queryKey: ['products'] }),
    ]);
  };
}

export function useAddProduct() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (body: MyProductAddBody) => addMyProduct(body),
    onSuccess: refresh,
  });
}

export function usePatchProduct() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: MyProductPatchBody }) =>
      patchMyProduct(id, body),
    onSuccess: refresh,
  });
}

export function useDeleteProduct() {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: (id: number) => deleteMyProduct(id),
    onSuccess: refresh,
  });
}
