import { useState } from 'react';
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
      </div>

      <Modal open={modal} title="A modal" onClose={() => setModal(false)}>
        Content of the modal.
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
