import { useState } from 'react';
import { basicRune, champion, foilCommon, noImage, noPrice, token } from '@/test/fixtures/cards';
import {
  AbilityText,
  BanBadge,
  CardArtPlaceholder,
  CardImage,
  DomainPips,
  PriceTag,
  RarityDot,
} from '@/components/card';
import { PriceChart, Sparkline } from '@/components/charts';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Icon } from '@/components/ui/Icon';
import { ICONS, type IconName } from '@/components/ui/icons';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel } from '@/components/ui/Panel';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { SettingsCard, SettingsRow } from '@/components/ui/SettingsCard';
import { Sheet } from '@/components/ui/Sheet';
import { Skeleton } from '@/components/ui/Skeleton';
import { Slider } from '@/components/ui/Slider';
import { Switch } from '@/components/ui/Switch';
import { pushToast } from '@/components/ui/toastStore';

/**
 * Every primitive on one page, for looking at them side by side and for screenshots. The route
 * exists only in development (`import.meta.env.DEV`); the production table has no `/_kitchen`.
 */
export function KitchenSink() {
  const [segment, setSegment] = useState('b');
  const [on, setOn] = useState(true);
  const [level, setLevel] = useState(60);
  const [modal, setModal] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [confirm, setConfirm] = useState(false);

  return (
    <>
      <PageHeader title="Kitchen sink" subtitle="Development only" />
      <div style={{ display: 'grid', gap: 'var(--gap)' }}>
        <Panel title="Buttons and badges">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
            <Button>Primary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger">Danger</Button>
            <Button size="sm">Small</Button>
            <Button pending>Pending</Button>
            <Badge>Neutral</Badge>
            <Badge tone="accent">Accent</Badge>
            <Badge tone="success">Success</Badge>
            <Badge tone="warning">Warning</Badge>
            <Badge tone="danger">Danger</Badge>
            <Avatar name="Jordan Vale" />
          </div>
        </Panel>

        <SettingsCard title="Form controls" description="Field, Input, Select, Switch, Slider">
          <SettingsRow>
            <Field label="Input" hint="A hint">
              {(props) => <Input {...props} placeholder="Type here" />}
            </Field>
            <Field label="Select">
              {(props) => (
                <Select {...props}>
                  <option>One</option>
                  <option>Two</option>
                </Select>
              )}
            </Field>
          </SettingsRow>
          <SettingsRow>
            <SegmentedControl
              label="Segmented"
              options={[
                { value: 'a', label: 'A' },
                { value: 'b', label: 'B' },
                { value: 'c', label: 'C' },
              ]}
              value={segment}
              onChange={setSegment}
            />
            <Switch label="Switch" checked={on} onCheckedChange={setOn} />
            <Checkbox label="Checkbox" defaultChecked />
          </SettingsRow>
          <SettingsRow>
            <Slider label="Slider" value={level} unit="%" onChange={setLevel} />
          </SettingsRow>
        </SettingsCard>

        <Panel title="Overlays and toasts">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <Button variant="ghost" onClick={() => setModal(true)}>
              Modal
            </Button>
            <Button variant="ghost" onClick={() => setSheet(true)}>
              Sheet
            </Button>
            <Button variant="ghost" onClick={() => setConfirm(true)}>
              Confirm
            </Button>
            <Button
              variant="ghost"
              onClick={() => pushToast({ kind: 'success', message: 'Saved' })}
            >
              Toast
            </Button>
            <Button
              variant="ghost"
              onClick={() =>
                pushToast({
                  kind: 'error',
                  message: 'Something failed',
                  action: { label: 'Retry', onAction: () => {} },
                })
              }
            >
              Toast with action
            </Button>
          </div>
        </Panel>

        <Panel title="States">
          <Skeleton label="Loading" />
          <EmptyState icon="collection" title="Nothing here yet" body="Add your first card." />
          <ErrorState message="Could not load" onRetry={() => {}} />
        </Panel>

        <Panel title="Icons">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
            {(Object.keys(ICONS) as IconName[]).map((name) => (
              <Icon key={name} name={name} size={24} title={name} />
            ))}
          </div>
        </Panel>

        <CardAtomsPanel />
      </div>

      <Modal open={modal} title="A modal" onClose={() => setModal(false)}>
        Content of the modal.
      </Modal>
      <Modal open={false} title="Unused" onClose={() => {}} size="lg">
        lg placeholder
      </Modal>
      <Modal open={false} title="Unused" onClose={() => {}} size="xl">
        xl placeholder
      </Modal>
      <Sheet open={sheet} title="A sheet" onClose={() => setSheet(false)}>
        Content of the sheet.
      </Sheet>
      <ConfirmDialog
        open={confirm}
        title="Delete it?"
        message="This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        danger
        onConfirm={() => setConfirm(false)}
        onCancel={() => setConfirm(false)}
      />
    </>
  );
}

const fixtures = [
  { name: 'champion', card: champion },
  { name: 'foilCommon', card: foilCommon },
  { name: 'basicRune', card: basicRune },
  { name: 'token', card: token },
  { name: 'noImage', card: noImage },
  { name: 'noPrice', card: noPrice },
];

function CardAtomsPanel() {
  return (
    <>
      <Panel title="Charts">
        <div style={{ display: 'grid', gap: 'var(--gap)' }}>
          <Sparkline values={[1, 2, 3, 2, 4]} label="Trend up" />
          <Sparkline values={[4, 3, 2, 3, 1]} label="Trend down" />
          <PriceChart
            points={[
              {
                date: '2026-07-22',
                market: 1.04,
                low: 0.98,
                avg7: 1,
                avg30: 1.01,
                market_foil: 2.1,
              },
              {
                date: '2026-08-22',
                market: 1.12,
                low: 1.05,
                avg7: 1.08,
                avg30: 1.06,
                market_foil: 2.3,
              },
              {
                date: '2026-09-22',
                market: 1.08,
                low: 1.02,
                avg7: 1.05,
                avg30: 1.07,
                market_foil: 2.2,
              },
              {
                date: '2026-10-22',
                market: 1.21,
                low: 1.15,
                avg7: 1.17,
                avg30: 1.16,
                market_foil: 2.45,
              },
            ]}
            series={['market', 'market_foil']}
            title="Kitchen price history"
          />
        </div>
      </Panel>

      <Panel title="Card atoms">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap: 'var(--gap)',
          }}
        >
          {fixtures.map(({ name, card }) => (
            <div key={name} style={{ display: 'grid', gap: 8 }}>
              <CardImage card={card} size="tile" />
              <div style={{ fontSize: 12, color: 'var(--muted-2)' }}>{name}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Card placeholders">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap: 'var(--gap)',
          }}
        >
          {fixtures.map(({ name, card }) => (
            <div key={name} style={{ display: 'grid', gap: 8 }}>
              <CardArtPlaceholder card={card} />
              <div style={{ fontSize: 12, color: 'var(--muted-2)' }}>{name}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Domain pips, rarity and bans">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <DomainPips domains={['Fury', 'Chaos']} />
          <DomainPips domains={['Mind']} />
          <DomainPips domains={[]} />
          <RarityDot rarity="Rare" />
          <RarityDot rarity="Rare" showLabel />
          <BanBadge bans={{ '1v1': true, '2v2': false }} />
          <BanBadge bans={{ '1v1': true, '2v2': true }} variant="compact" />
        </div>
      </Panel>

      <Panel title="Ability text">
        <div style={{ display: 'grid', gap: 12 }}>
          <AbilityText text="[Accelerate] When I attack, deal 2." />
          <AbilityText text="Pay :rb_energy_2: (then :rb_exhaust:)." />
          <AbilityText text=":rb_rune_fury: :rb_rune_rainbow: :rb_power:" />
        </div>
      </Panel>

      <Panel title="Price tags">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <PriceTag price={champion.price} />
          <PriceTag price={champion.price} trend="30d" />
          <PriceTag price={null} />
          <PriceTag price={{ ...champion.price!, market_foil: 2.5 }} foil />
        </div>
      </Panel>
    </>
  );
}
