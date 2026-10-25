import { useState } from 'react';
import type { CatalogItem } from '../types';
import { editorStore } from './store';
import { artifacts } from './lifecycle';
import { errorMessage } from '../lib/validation';

export function useTemplateUpgrade(onNotice: (message: string, error?: boolean) => void) {
  const [busy, setBusy] = useState(false);
  const apply = async (nodeId: string, template: CatalogItem) => {
    setBusy(true);
    editorStore.getState().upgradeNode(nodeId, template);
    try {
      const result = await artifacts.validation();
      if (!result) {
        const validation = artifacts.store.getState().validation;
        if (validation.status === 'failed')
          onNotice(`Template updated; validation failed: ${validation.error}`, true);
        return;
      }
      if (result)
        onNotice(
          result.conforms
            ? 'Template updated; validation passed.'
            : `Template updated: ${result.issue_count} validation issues.`,
          !result.conforms,
        );
    } catch (error) {
      onNotice(`Template updated; validation failed: ${errorMessage(error)}`, true);
    } finally {
      setBusy(false);
    }
  };
  return { apply, busy };
}
