import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';

export function ModalDialog({
  title,
  description,
  onClose,
  children,
  busy = false,
}: {
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
  busy?: boolean;
}) {
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="app-dialog-overlay" />
        <Dialog.Content className="app-dialog">
          <div className="app-dialog-head">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>{description}</Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" disabled={busy} aria-label="Close dialog">
              <X size={20} />
            </Dialog.Close>
          </div>
          <div className="app-dialog-body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
