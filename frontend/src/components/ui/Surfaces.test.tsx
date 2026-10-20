import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Avatar, initialsOf } from './Avatar';
import { Badge } from './Badge';
import { EmptyState } from './EmptyState';
import { PageHeader } from './PageHeader';
import { Panel } from './Panel';
import { SettingsCard } from './SettingsCard';

describe('initialsOf', () => {
  it.each([
    ['Jordan Vale', 'JV'],
    ['ada lovelace byron', 'AL'],
    ['ada_lovelace', 'AL'],
    ['ada', 'AD'],
    ['x', 'X'],
    ['  maría  ', 'MA'],
    ['', '?'],
    ['   ', '?'],
  ])('%j gives %j', (name, initials) => {
    expect(initialsOf(name)).toBe(initials);
  });
});

describe('Avatar (DS-8)', () => {
  it('shows the initials and is decorative by default', () => {
    const { container } = render(<Avatar name="Jordan Vale" />);
    expect(screen.getByText('JV')).toBeVisible();
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
  });

  it('exposes a name when asked', () => {
    render(<Avatar name="ada" label="Cuenta de ada" />);
    expect(screen.getByRole('img', { name: 'Cuenta de ada' })).toHaveTextContent('AD');
  });
});

describe('Panel (DS-8)', () => {
  it('is a named region when it has a title', () => {
    render(<Panel title="Resumen">contenido</Panel>);
    expect(screen.getByRole('region', { name: 'Resumen' })).toHaveTextContent('contenido');
    expect(screen.getByRole('heading', { level: 2, name: 'Resumen' })).toBeVisible();
  });

  it('is just a container without a title', () => {
    render(<Panel>solo contenido</Panel>);
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    expect(screen.getByText('solo contenido')).toBeVisible();
  });
});

describe('PageHeader (DS-8)', () => {
  it('has the page heading, a subtitle and actions', () => {
    render(
      <PageHeader
        title="Interfaz"
        subtitle="Personaliza la app"
        actions={<button>Guardar</button>}
      />,
    );
    expect(screen.getByRole('heading', { level: 1, name: 'Interfaz' })).toBeVisible();
    expect(screen.getByText('Personaliza la app')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeVisible();
  });

  it('works with the title alone', () => {
    render(<PageHeader title="Inicio" />);
    expect(screen.getByRole('heading', { level: 1, name: 'Inicio' })).toBeVisible();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});

describe('Badge (DS-8)', () => {
  it.each(['neutral', 'accent', 'success', 'warning', 'danger'] as const)(
    'renders its text in the %s tone',
    (tone) => {
      render(<Badge tone={tone}>Nuevo</Badge>);
      expect(screen.getByText('Nuevo')).toBeVisible();
    },
  );
});

describe('SettingsCard (DS-8)', () => {
  it('is a region named by its title, with a description and its controls', () => {
    render(
      <SettingsCard title="Apariencia" description="Cómo se ve la app">
        <button>Control</button>
      </SettingsCard>,
    );
    const region = screen.getByRole('region', { name: 'Apariencia' });
    expect(region).toHaveTextContent('Cómo se ve la app');
    expect(region).toContainElement(screen.getByRole('button', { name: 'Control' }));
  });
});

describe('EmptyState (DS-8)', () => {
  it('says what is empty and offers the next step', async () => {
    const onAction = vi.fn();
    render(
      <EmptyState
        icon="collection"
        title="Aún no hay cartas"
        body="Añade tu primera carta"
        action={{ label: 'Añadir carta', onAction }}
      />,
    );
    expect(screen.getByRole('heading', { name: 'Aún no hay cartas' })).toBeVisible();
    expect(screen.getByText('Añade tu primera carta')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Añadir carta' }));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it('has no button without an action', () => {
    render(<EmptyState title="Nada por aquí" />);
    expect(screen.getByRole('heading', { name: 'Nada por aquí' })).toBeVisible();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
