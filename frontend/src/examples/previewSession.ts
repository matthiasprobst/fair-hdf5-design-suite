import { ProjectEditorSession } from '../projects/editorSession';
import type { Example } from './api';
import type { Capabilities } from '../editor/limits';
import type { Catalog } from '../types';

/** Read-only workbench: no reservation, polling, autosave, or recovery writes. */
export class ExamplePreviewSession extends ProjectEditorSession {
  constructor(example: Example, catalog: Catalog, capabilities: Capabilities, userId: string) {
    super(
      {
        id: `example-${example.id}`,
        name: example.name,
        description: example.description,
        owner_id: 'example-library',
        owner_name: 'Example library',
        role: 'viewer',
        shared: false,
        revision: 1,
        created_at: 0,
        updated_at: 0,
        blueprint: example.blueprint,
        edit_lock: null,
      },
      catalog,
      capabilities,
      userId,
    );
    this.state.setState({ recovery: null, recoveryAvailable: false, status: 'Read-only example' });
  }
  override start() {
    const stopArtifacts = this.artifacts.start();
    const stopCsv = this.csv.start();
    return () => {
      stopArtifacts();
      stopCsv();
    };
  }
}
