import { createStore } from 'zustand/vanilla';
import { createEditorStore } from '../editor/store';
import { createArtifacts } from '../editor/artifacts';
import { createCsvSession } from '../editor/csvSession';
import { parseBlueprint, toBlueprint } from '../editor/adapters';
import type { Capabilities } from '../editor/limits';
import type { Blueprint, Catalog, TemplateDraft, TemplateSnapshot } from '../types';
import type { Project } from './types';
import { projectApi } from './api';
import { ApiError } from '../lib/http';
import { errorMessage } from '../lib/validation';

export interface ProjectSessionState {
  project: Project;
  mode: 'view' | 'editing' | 'paused';
  status: string;
  error: string;
  dirty: boolean;
  busy: boolean;
  recovery: string | null;
  recoveryAvailable: boolean;
  accessLost: boolean;
}
export function draftKey(userId: string, projectId: string) {
  return `fair-hdf5-project-v1:${userId}:${projectId}`;
}

/** One tab owns one controller. All content writes pass through its serial queue. */
export class ProjectEditorSession {
  readonly state;
  readonly graph;
  readonly artifacts;
  readonly csv;
  private token: string | null = null;
  private expires = 0;
  private queue: Promise<void> = Promise.resolve();
  private saveTimer: ReturnType<typeof setTimeout> | undefined;
  private stopped = false;
  private suppress = false;
  private generation = 0;
  private archived = false;
  private ending = false;
  private baseRevision: number;
  private readonly key: string;
  private readonly editorId = crypto.randomUUID();

  constructor(project: Project, catalog: Catalog, capabilities: Capabilities, userId: string) {
    this.baseRevision = project.revision;
    this.key = draftKey(userId, project.id);
    let recovery = null;
    try {
      recovery = localStorage.getItem(this.key);
    } catch {
      /* Report writes if browser storage is unavailable. */
    }
    this.state = createStore<ProjectSessionState>(() => ({
      project,
      mode: 'view',
      status: 'Saved on server',
      error: '',
      dirty: false,
      busy: false,
      recovery,
      recoveryAvailable: recovery !== null,
      accessLost: false,
    }));
    this.graph = createEditorStore(() => this.canEdit());
    this.graph.getState().setCapabilities(capabilities);
    this.graph.getState().hydrate(project.blueprint, catalog);
    this.artifacts = createArtifacts(this.graph);
    this.csv = createCsvSession(this.graph);
  }

  canEdit() {
    return !this.ending && this.hasLease();
  }

  private hasLease() {
    return (
      !this.stopped &&
      this.state.getState().mode === 'editing' &&
      this.state.getState().project.role !== 'viewer' &&
      this.token !== null &&
      Date.now() / 1000 < this.expires - 5
    );
  }

  start() {
    this.stopped = false;
    const stopArtifacts = this.artifacts.start();
    const stopCsv = this.csv.start();
    const stopAccess = this.state.subscribe((s) => {
      if (s.accessLost) this.csv.clear();
    });
    const unsubscribe = this.graph.subscribe((state, previous) => {
      if (this.suppress) return;
      if (state.saveRevision === previous.saveRevision) {
        if (state.nodes.some((node, index) => node.position !== previous.nodes[index]?.position)) {
          this.generation++;
          this.state.setState({ dirty: true, status: 'Unsaved changes' });
        }
        return;
      }
      this.generation++;
      this.state.setState({ dirty: true, status: 'Unsaved changes' });
      this.persist();
      clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => {
        void this.save().catch(() => {});
      }, 600);
    });
    let renewing = false,
      checking = false;
    const heartbeat = setInterval(() => {
      if (!this.token || this.state.getState().mode !== 'editing' || renewing) return;
      renewing = true;
      const token = this.token;
      void projectApi
        .renew(this.state.getState().project.id, token)
        .then((expires) => {
          if (!this.stopped && this.token === token && this.state.getState().mode === 'editing')
            this.expires = expires;
        })
        .catch((e) => {
          if (!this.stopped && this.token === token) this.pause(e);
        })
        .finally(() => {
          renewing = false;
        });
    }, 30_000);
    const poll = setInterval(() => {
      if (
        this.token &&
        Date.now() / 1000 >= this.expires - 5 &&
        this.state.getState().mode === 'editing'
      )
        this.pause(new Error('The editing reservation expired. Your draft is preserved.'));
      if (this.state.getState().mode !== 'view' || checking) return;
      checking = true;
      void this.refresh()
        .catch((e) => {
          if (!this.stopped) this.state.setState({ error: errorMessage(e) });
        })
        .finally(() => {
          checking = false;
        });
    }, 15_000);
    const beforeUnload = (e: BeforeUnloadEvent) => {
      if (this.state.getState().dirty) {
        this.persist();
        e.preventDefault();
        e.returnValue = '';
      }
    };
    const hide = () => {
      if (this.state.getState().dirty) this.persist();
      if (this.token && !this.state.getState().dirty)
        void projectApi.release(this.state.getState().project.id, this.token, true).catch(() => {});
    };
    window.addEventListener('beforeunload', beforeUnload);
    window.addEventListener('pagehide', hide);
    return () => {
      this.stopped = true;
      clearTimeout(this.saveTimer);
      clearInterval(heartbeat);
      clearInterval(poll);
      unsubscribe();
      stopArtifacts();
      stopCsv();
      stopAccess();
      window.removeEventListener('beforeunload', beforeUnload);
      window.removeEventListener('pagehide', hide);
      if (this.state.getState().dirty) this.persist();
      const token = this.token;
      this.token = null;
      if (token)
        void projectApi.release(this.state.getState().project.id, token, true).catch(() => {});
    };
  }

  async refresh(force = false) {
    let project: Project;
    try {
      project = await projectApi.get(
        this.state.getState().project.id,
        this.graph.getState().catalog,
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 404 && !this.stopped)
        this.state.setState({ accessLost: true });
      throw error;
    }
    if (this.stopped) return;
    if (this.state.getState().mode !== 'view') {
      this.state.setState((s) => ({
        project: {
          ...s.project,
          shared: project.shared,
          role: project.role,
          owner_name: project.owner_name,
          edit_lock: project.edit_lock,
        },
      }));
      if (project.role === 'viewer' && this.state.getState().mode === 'editing')
        this.pause(
          new ApiError(
            403,
            'read_only',
            'Your access changed to view only. Your draft is preserved.',
          ),
        );
      return;
    }
    if ((force || project.revision !== this.baseRevision) && !this.state.getState().dirty) {
      const { catalog } = await projectApi.catalog(project.id);
      if (this.stopped || this.state.getState().mode !== 'view') return;
      this.graph.getState().setCatalog(catalog);
      this.hydrate(project);
    }
    this.state.setState({ project, error: '' });
  }

  private hydrate(project: Project) {
    this.suppress = true;
    this.graph.getState().hydrate(project.blueprint);
    this.suppress = false;
    this.baseRevision = project.revision;
  }

  async edit() {
    if (this.state.getState().busy) return;
    this.state.setState({ busy: true, error: '' });
    const id = this.state.getState().project.id;
    try {
      const lease =
        this.token && this.state.getState().mode === 'paused'
          ? { token: this.token, expires_at: await projectApi.renew(id, this.token) }
          : await projectApi.acquire(id, this.editorId);
      this.token = lease.token;
      this.expires = lease.expires_at;
      const [{ catalog }] = await Promise.all([projectApi.catalog(id)]);
      const project = await projectApi.get(id, catalog);
      if (this.stopped) {
        await projectApi.release(id, lease.token);
        return;
      }
      if (this.state.getState().dirty && this.baseRevision !== project.revision) {
        await projectApi.release(id, lease.token);
        this.token = null;
        throw new Error(
          'The server has newer changes. Export your draft or save it as a private copy before loading the server version.',
        );
      }
      this.graph.getState().setCatalog(catalog);
      if (!this.state.getState().dirty) this.hydrate(project);
      this.state.setState({
        project,
        mode: 'editing',
        status: this.state.getState().dirty ? 'Unsaved changes' : 'Saved on server',
      });
      if (this.state.getState().dirty) await this.save();
    } catch (e) {
      const token = this.token;
      this.token = null;
      if (token) void projectApi.release(id, token).catch(() => {});
      this.state.setState({ error: errorMessage(e) });
    } finally {
      this.state.setState({ busy: false });
    }
  }

  private enqueue(work: () => Promise<void>) {
    const next = this.queue.catch(() => {}).then(work);
    this.queue = next;
    return next;
  }

  private async savePending() {
    while (this.state.getState().dirty) {
      if (!this.hasLease() || !this.token)
        throw new Error('Editing is paused. Your draft is preserved.');
      if (this.graph.getState().nodes.some((node) => node.dragging)) return;
      const state = this.graph.getState(),
        generation = this.generation;
      this.state.setState({ status: 'Saving…' });
      try {
        const saved = await projectApi.save(
          this.state.getState().project.id,
          this.token,
          this.baseRevision,
          toBlueprint(state),
          this.state.getState().project.description,
          state.catalog,
        );
        if (this.stopped) return;
        this.baseRevision = saved.revision;
        const dirty = this.generation !== generation;
        this.state.setState((s) => ({
          project: dirty ? { ...saved, description: s.project.description } : saved,
          dirty,
          status: dirty ? 'Unsaved changes' : 'Saved on server',
          error: '',
        }));
        if (dirty) this.persist();
        else this.clearDraft();
      } catch (e) {
        if (e instanceof ApiError && [413, 422].includes(e.status)) {
          this.persist();
          this.state.setState({ error: errorMessage(e), status: 'Unsaved changes' });
        } else this.pause(e);
        throw e;
      }
    }
  }

  save() {
    clearTimeout(this.saveTimer);
    return this.enqueue(() => this.savePending());
  }

  async finish() {
    this.ending = true;
    this.state.setState({ busy: true });
    try {
      await this.save();
      if (this.state.getState().dirty) throw new Error('Finish moving the block before leaving.');
      if (this.token) await projectApi.release(this.state.getState().project.id, this.token);
      this.token = null;
      this.state.setState({ mode: 'view', error: '', status: 'Saved on server' });
      await this.refresh(true);
    } finally {
      this.ending = false;
      this.state.setState({ busy: false });
    }
  }

  async publish(
    template: TemplateDraft,
    templateId?: string,
    templateRevision?: number,
    signal?: AbortSignal,
  ) {
    let result: TemplateSnapshot | undefined;
    await this.enqueue(async () => {
      await this.savePending();
      if (!this.canEdit() || !this.token)
        throw new Error('Start editing before changing project templates.');
      const saved = await projectApi.publish(
        this.state.getState().project.id,
        this.token,
        this.baseRevision,
        template,
        templateId,
        templateRevision,
        signal,
      );
      this.baseRevision = saved.revision;
      this.state.setState((s) => ({ project: { ...s.project, revision: saved.revision } }));
      result = saved.template;
    });
    if (!result) throw new Error('Template was not saved.');
    return result;
  }

  private pause(error: unknown) {
    if (this.stopped) return;
    this.persist();
    this.state.setState({ mode: 'paused', status: 'Editing paused', error: errorMessage(error) });
    if (error instanceof ApiError && error.status === 404)
      this.state.setState({ accessLost: true });
    if (error instanceof ApiError && [401, 403, 404, 423].includes(error.status)) this.token = null;
  }

  setDescription(description: string) {
    if (!this.canEdit()) return;
    this.generation++;
    this.state.setState((s) => ({
      project: { ...s.project, description },
      dirty: true,
      status: 'Unsaved changes',
    }));
    this.persist();
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => {
      void this.save().catch(() => {});
    }, 600);
  }

  private persist() {
    if (!this.state.getState().dirty) return;
    try {
      if (!this.archived) {
        const previous = localStorage.getItem(this.key);
        if (previous !== null) localStorage.setItem(`${this.key}:original`, previous);
        this.archived = true;
      }
      const raw = JSON.stringify({
        version: 1,
        base_revision: this.baseRevision,
        blueprint: toBlueprint(this.graph.getState()),
        description: this.state.getState().project.description,
      });
      localStorage.setItem(this.key, raw);
      this.state.setState({ recovery: raw });
    } catch {
      this.state.setState({
        error: 'Local recovery is unavailable. Export JSON to preserve your work.',
      });
    }
  }

  private clearDraft() {
    try {
      localStorage.removeItem(this.key);
      this.state.setState({ recovery: null, recoveryAvailable: false });
    } catch {
      /* The server save is confirmed. */
    }
  }

  restore() {
    if (!this.canEdit()) return;
    const raw = this.state.getState().recovery;
    if (!raw) return;
    try {
      const draft = JSON.parse(raw);
      if (draft.version !== 1 || draft.base_revision !== this.baseRevision)
        throw new Error(
          'This recovery draft is based on an older server version. Export it or save it as a private copy.',
        );
      const blueprint = parseBlueprint(draft.blueprint, this.graph.getState().catalog);
      this.state.setState({ recoveryAvailable: false });
      this.graph.getState().replace(blueprint);
      if (typeof draft.description === 'string') this.setDescription(draft.description);
    } catch (e) {
      this.state.setState({ error: errorMessage(e) });
    }
  }

  async saveCopy() {
    const raw = this.state.getState().recovery;
    const content: Blueprint =
      this.state.getState().dirty || !raw
        ? toBlueprint(this.graph.getState())
        : parseBlueprint(JSON.parse(raw).blueprint, this.graph.getState().catalog);
    return projectApi.create({
      name: `${content.name.slice(0, 150)} (copy)`,
      blueprint: content,
      description: this.state.getState().project.description,
    });
  }

  async discard() {
    clearTimeout(this.saveTimer);
    await this.queue.catch(() => {});
    this.state.setState({ dirty: false, mode: 'view' });
    this.clearDraft();
    if (this.token) {
      await projectApi.release(this.state.getState().project.id, this.token).catch(() => {});
      this.token = null;
    }
    try {
      await this.refresh(true);
    } catch (error) {
      this.state.setState({ error: errorMessage(error) });
    }
  }
}
