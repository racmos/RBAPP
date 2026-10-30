import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { http } from 'msw';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { describe, expect, it } from 'vitest';
import { API, NO_PREFS, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { useSearchNavigation } from './useSearchNavigation';

const LONG = { timeout: 10000 };

/** Shows `current()` and adds `key=value` to it on each button. */
function Probe() {
  const { current, go } = useSearchNavigation();
  const add = (key: string) => {
    const next = current();
    next.set(key, '1');
    go(next.toString());
  };
  return (
    <>
      <button type="button" onClick={() => add('a')}>
        a
      </button>
      <button type="button" onClick={() => add('b')}>
        b
      </button>
      <output>{current().toString()}</output>
    </>
  );
}

function renderProbe(path: string) {
  const router = createMemoryRouter([{ path: '/', element: <Probe /> }], {
    initialEntries: [path],
  });
  render(<RouterProvider router={router} />);
  return router;
}

describe('useSearchNavigation (L6)', () => {
  it('builds on the last search asked for, before the page renders it', async () => {
    const router = renderProbe('/?q=x');
    act(() => {
      fireEvent.click(screen.getByRole('button', { name: 'a' }));
      fireEvent.click(screen.getByRole('button', { name: 'b' }));
    });
    await waitFor(() => expect(router.state.location.search).toBe('?q=x&a=1&b=1'));
  });

  it('follows the rendered location after back and forward', async () => {
    const router = renderProbe('/?q=x');
    fireEvent.click(screen.getByRole('button', { name: 'a' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('q=x&a=1'));
    await act(() => router.navigate(-1));
    await waitFor(() => expect(router.state.location.search).toBe('?q=x'));
    fireEvent.click(screen.getByRole('button', { name: 'b' }));
    await waitFor(() => expect(router.state.location.search).toBe('?q=x&b=1'));
  });

  it('keeps a collection change that the page has not rendered yet', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession(NO_PREFS)));
    const { where } = await renderApp({ path: '/collection', width: 1280 });
    await screen.findByRole('table', { name: 'Tu colección agrupada por carta' }, LONG);
    const byName = within(screen.getByRole('columnheader', { name: 'Nombre' })).getByRole('button');
    const perPage = screen.getByRole('combobox', { name: 'Por página' });
    // the router applies a navigation in a transition: the second change comes before the render
    act(() => {
      fireEvent.click(byName);
      fireEvent.change(perPage, { target: { value: '100' } });
    });
    await waitFor(() => expect(where()).toBe('/collection?sort=name&per_page=100'), LONG);
  }, 20000);
});

/** `setSearchParams` with react-router's functional signature, as the admin lists use it. */
function SetterProbe() {
  const { setSearchParams } = useSearchNavigation();
  const add = (key: string) =>
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set(key, '1');
        return next;
      },
      { replace: true },
    );
  return (
    <button
      type="button"
      onClick={() => {
        add('a');
        add('b');
      }}
    >
      both
    </button>
  );
}

describe('useSearchNavigation setSearchParams (admin lists)', () => {
  it('builds each change on the latest search asked for', async () => {
    const router = createMemoryRouter([{ path: '/', element: <SetterProbe /> }], {
      initialEntries: ['/?q=x'],
    });
    render(<RouterProvider router={router} />);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'both' }));
    });
    await waitFor(() => expect(router.state.location.search).toBe('?q=x&a=1&b=1'), LONG);
  });
});

/** Returns the search it was given: a no-op change, as the admin search effects send. */
function NoOpProbe() {
  const { setSearchParams } = useSearchNavigation();
  return (
    <button
      type="button"
      onClick={() => setSearchParams((previous) => previous, { replace: true })}
    >
      same
    </button>
  );
}

describe('useSearchNavigation no-op changes', () => {
  it('does not navigate when the search does not change (a navigation remounts the page)', async () => {
    const router = createMemoryRouter([{ path: '/', element: <NoOpProbe /> }], {
      initialEntries: ['/?q=x'],
    });
    render(<RouterProvider router={router} />);
    const key = router.state.location.key;
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'same' }));
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(router.state.location.key).toBe(key);
    expect(router.state.location.search).toBe('?q=x');
  });
});
