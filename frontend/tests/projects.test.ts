import test, { mock } from 'node:test';
import type { TestContext } from 'node:test';
import assert from 'node:assert/strict';
import { createEditorStore } from '../src/editor/store';
import { toBlueprint } from '../src/editor/adapters';
import { parseSession, parseSummary, parseLock, projectApi } from '../src/projects/api';
import { ProjectEditorSession, draftKey } from '../src/projects/editorSession';
import { ApiError } from '../src/lib/http';
import { api } from '../src/lib/api';
import type { Project } from '../src/projects/types';
import type { Blueprint, Catalog, TemplateSnapshot } from '../src/types';

const capabilities = {
  max_nodes: 10,
  max_edges: 10,
  max_upload_bytes: 1000,
  shacl_engine: 'pyshacl' as const,
};
const blueprint: Blueprint = { name: 'Research', version: '0.1', nodes: [], edges: [] };
const project: Project = {
  id: 'project-one',
  name: 'Research',
  description: '',
  owner_id: 'alice',
  owner_name: 'Alice',
  role: 'owner',
  shared: false,
  revision: 1,
  created_at: 1,
  updated_at: 1,
  blueprint,
  edit_lock: null,
};
function setup(t: TestContext, initial = project) {
  const values = new Map<string, string>();
  const storage = {
    getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => {
      values.set(k, v);
    },
    removeItem: (k: string) => {
      values.delete(k);
    },
  };
  const previousStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: new EventTarget() });
  t.after(() => {
    stopSession();
    if (previousStorage) Object.defineProperty(globalThis, 'localStorage', previousStorage);
    else Reflect.deleteProperty(globalThis, 'localStorage');
    if (previousWindow) Object.defineProperty(globalThis, 'window', previousWindow);
    else Reflect.deleteProperty(globalThis, 'window');
    mock.restoreAll();
  });
  let server = structuredClone(initial);
  mock.method(projectApi, 'get', async () => structuredClone(server));
  mock.method(projectApi, 'catalog', async () => ({ catalog: {}, profile_source: 'Test' }));
  const acquire = mock.method(projectApi, 'acquire', async () => ({
    token: 'lease-one',
    expires_at: Date.now() / 1000 + 120,
    revision: server.revision,
  }));
  mock.method(projectApi, 'release', async () => new Response('{}'));
  mock.method(api, 'preview', async () => ({
    objects: [],
    profiles: 0,
    node_count: 0,
    edge_count: 0,
  }));
  const save = mock.method(
    projectApi,
    'save',
    async (
      _id: string,
      _token: string,
      expected: number,
      content: Blueprint,
      description: string,
    ) => {
      assert.equal(expected, server.revision);
      server = {
        ...server,
        name: content.name,
        blueprint: structuredClone(content),
        description,
        revision: expected + 1,
      };
      return structuredClone(server);
    },
  );
  const session = new ProjectEditorSession(structuredClone(initial), {}, capabilities, 'alice');
  const stopSession = session.start();
  return {
    session,
    values,
    save,
    acquire,
    stopSession,
    setServer: (value: Project) => {
      server = value;
    },
    getServer: () => server,
  };
}

test('read-only stores reject content changes while permitting selection and measurements', () => {
  let editable = true;
  const store = createEditorStore(() => editable);
  store.getState().setCapabilities(capabilities);
  store.getState().hydrate({
    ...blueprint,
    nodes: [{ id: 'one', type: 'group', label: 'Group', x: 0, y: 0, config: { path: '' } }],
  });
  editable = false;
  const original = toBlueprint(store.getState()),
    revision = store.getState().saveRevision;
  store.getState().rename('Changed');
  store.getState().replace({ ...blueprint, name: 'Replacement' });
  store.getState().updateNode('one', { label: 'Changed' });
  store.getState().deleteElements(['one']);
  store.getState().duplicateNode('one');
  store.getState().onNodesChange([
    { type: 'position', id: 'one', position: { x: 12, y: 15 } },
    { type: 'remove', id: 'one' },
  ]);
  assert.deepEqual(toBlueprint(store.getState()), original);
  store.getState().onNodesChange([
    { type: 'select', id: 'one', selected: true },
    { type: 'dimensions', id: 'one', dimensions: { width: 100, height: 80 } },
  ]);
  assert.equal(store.getState().nodes[0].selected, true);
  assert.equal(store.getState().saveRevision, revision);
  editable = true;
  store.getState().rename('Allowed');
  assert.equal(store.getState().name, 'Allowed');
});

test('project contracts reject malformed identities, roles and lock expiry', () => {
  assert.throws(() =>
    parseSession({
      user: { username: 'fake' },
      csrf_token: 'token',
      password_policy: { min_length: 15, max_length: 128 },
    }),
  );
  assert.throws(() => parseSummary({ ...project, role: 'admin' }));
  assert.throws(() => parseSummary({ ...project, revision: 0 }));
  assert.throws(() => parseSummary({ ...project, example_id: 123 }));
  assert.equal(
    parseSummary({ ...project, example_id: 'csv-measurements' }).example_id,
    'csv-measurements',
  );
  assert.throws(() =>
    parseLock({ user_id: 'alice', display_name: 'Alice', expires_at: 'tomorrow' }),
  );
  assert.equal(parseLock(null), null);
  assert.notEqual(draftKey('alice', 'one'), draftKey('bob', 'one'));
  assert.notEqual(draftKey('alice', 'one'), draftKey('alice', 'two'));
});

test('session contracts carry and validate the server password policy', () => {
  const session = { user: null, csrf_token: 'token' };
  for (const minimum of [3, 15, 128]) {
    const password_policy = { min_length: minimum, max_length: 128 };
    assert.deepEqual(parseSession({ ...session, password_policy }), {
      ...session,
      password_policy,
    });
  }
  for (const password_policy of [
    undefined,
    null,
    {},
    { min_length: '3', max_length: 128 },
    { min_length: 2, max_length: 128 },
    { min_length: 129, max_length: 128 },
    { min_length: 3.5, max_length: 128 },
    { min_length: NaN, max_length: 128 },
    { min_length: Infinity, max_length: 128 },
    { min_length: 3, max_length: 127 },
  ]) {
    assert.throws(() => parseSession({ ...session, password_policy }));
  }
});

test('opening an unlocked project automatically reserves it without saving', async (t) => {
  const { session, save, acquire } = setup(t);
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(acquire.mock.callCount(), 1);
  assert.equal(session.state.getState().mode, 'editing');
  assert.equal(session.canEdit(), true);
  assert.equal(session.state.getState().dirty, false);
  assert.equal(save.mock.callCount(), 0);
  await session.finish();
  await session.refresh();
  assert.equal(session.state.getState().mode, 'view');
  assert.equal(acquire.mock.callCount(), 1, 'Finishing must not immediately reacquire the lock');
});

test('view-only projects never acquire a lease or save', async (t) => {
  const { session, save, acquire } = setup(t, { ...project, role: 'viewer' });
  await new Promise<void>((resolve) => setImmediate(resolve));
  session.graph.getState().rename('Not allowed');
  assert.equal(session.graph.getState().name, project.name);
  assert.equal(session.state.getState().dirty, false);
  await session.save();
  await session.edit();
  assert.equal(acquire.mock.callCount(), 0);
  assert.equal(save.mock.callCount(), 0);
});

test('editors automatically reserve projects with an expired lock snapshot', async (t) => {
  const { session, acquire } = setup(t, {
    ...project,
    role: 'editor',
    edit_lock: {
      user_id: 'bob',
      display_name: 'Bob',
      expires_at: Date.now() / 1000 - 1,
    },
  });
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(acquire.mock.callCount(), 1);
  assert.equal(session.canEdit(), true);
});

test('opening a reserved project remains read-only without attempting acquisition', async (t) => {
  const { session, acquire } = setup(t, {
    ...project,
    edit_lock: {
      user_id: 'alice',
      display_name: 'Alice',
      expires_at: Date.now() / 1000 + 120,
    },
  });
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(acquire.mock.callCount(), 0);
  assert.equal(session.canEdit(), false);
  assert.equal(session.state.getState().error, '');
});

test('a race for automatic reservation refreshes the lock and remains in view mode', async (t) => {
  const { session, setServer } = setup(t);
  const edit_lock = { user_id: 'bob', display_name: 'Bob', expires_at: Date.now() / 1000 + 120 };
  setServer({ ...project, edit_lock });
  mock.method(projectApi, 'acquire', async () => {
    throw new ApiError(423, 'project_locked', 'Bob is editing');
  });
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(session.state.getState().mode, 'view');
  assert.equal(session.state.getState().error, '');
  assert.deepEqual(session.state.getState().project.edit_lock, edit_lock);
});

test('automatic reservation failures leave an explicit retry available', async (t) => {
  const { session } = setup(t);
  mock.method(projectApi, 'acquire', async () => {
    throw new Error('Connection unavailable');
  });
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(session.state.getState().mode, 'view');
  assert.equal(session.state.getState().busy, false);
  assert.match(session.state.getState().error, /Connection unavailable/);
});

test('effect cleanup/restart acquires once and releases a late reservation on exit', async (t) => {
  const { session, stopSession, acquire } = setup(t);
  stopSession();
  const stop = session.start();
  let resolveLease!: (value: { token: string; expires_at: number; revision: number }) => void;
  const pendingAcquire = mock.method(
    projectApi,
    'acquire',
    () =>
      new Promise((resolve) => {
        resolveLease = resolve;
      }),
  );
  const release = mock.method(projectApi, 'release', async () => new Response('{}'));
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(acquire.mock.callCount(), 0, 'The replayed initial acquisition was cancelled');
  assert.equal(pendingAcquire.mock.callCount(), 1);
  stop();
  resolveLease({ token: 'late-lease', expires_at: Date.now() / 1000 + 120, revision: 1 });
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(release.mock.callCount(), 1);
  assert.equal(release.mock.calls[0].arguments[1], 'late-lease');
  assert.equal(session.canEdit(), false);
});

test('leaving during automatic catalog loading releases the acquired reservation', async (t) => {
  const { session, stopSession } = setup(t);
  let resolveCatalog!: (value: { catalog: Catalog; profile_source: string }) => void;
  mock.method(
    projectApi,
    'catalog',
    () =>
      new Promise((resolve) => {
        resolveCatalog = resolve;
      }),
  );
  const release = mock.method(projectApi, 'release', async () => new Response('{}'));
  await new Promise<void>((resolve) => setImmediate(resolve));
  stopSession();
  resolveCatalog({ catalog: {}, profile_source: 'Test' });
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(release.mock.callCount(), 1);
  assert.equal(session.canEdit(), false);
  assert.equal(session.state.getState().mode, 'view');
});

test('save queue preserves edits and description changes made during an in-flight save', async (t) => {
  const { session, setServer, getServer } = setup(t);
  await session.edit();
  const revisions: number[] = [];
  let resolveFirst: (() => void) | undefined;
  mock.method(
    projectApi,
    'save',
    async (
      _id: string,
      _token: string,
      revision: number,
      content: Blueprint,
      description: string,
    ) => {
      revisions.push(revision);
      if (revisions.length === 1)
        await new Promise<void>((resolve) => {
          resolveFirst = resolve;
        });
      const saved = {
        ...getServer(),
        blueprint: content,
        name: content.name,
        description,
        revision: revision + 1,
      };
      setServer(saved);
      return saved;
    },
  );
  session.graph.getState().rename('First edit');
  const pending = session.save();
  await new Promise<void>((resolve) => setImmediate(resolve));
  session.graph.getState().rename('Second edit');
  session.setDescription('Description typed during save');
  resolveFirst!();
  await pending;
  assert.deepEqual(revisions, [1, 2]);
  assert.equal(getServer().name, 'Second edit');
  assert.equal(getServer().description, 'Description typed during save');
  assert.equal(session.state.getState().dirty, false);
});

test('failed saves pause mutations and keep a user/project-specific recovery draft', async (t) => {
  const { session, values } = setup(t);
  await session.edit();
  mock.method(projectApi, 'save', async () => {
    throw new ApiError(423, 'lease_lost', 'Lease expired');
  });
  session.graph.getState().rename('Recover me');
  await assert.rejects(session.save(), /Lease expired/);
  assert.equal(session.state.getState().mode, 'paused');
  session.graph.getState().rename('Not accepted');
  assert.equal(session.graph.getState().name, 'Recover me');
  assert.equal(JSON.parse(values.get(draftKey('alice', project.id))!).blueprint.name, 'Recover me');
});

test('ending an editing session saves before releasing its lease', async (t) => {
  const { session } = setup(t);
  await session.edit();
  const sequence: string[] = [];
  mock.method(
    projectApi,
    'save',
    async (_id: string, _token: string, revision: number, content: Blueprint) => {
      sequence.push('save');
      return { ...project, blueprint: content, name: content.name, revision: revision + 1 };
    },
  );
  mock.method(projectApi, 'release', async () => {
    sequence.push('release');
    return new Response('{}');
  });
  session.graph.getState().rename('Final edit');
  await session.finish();
  assert.deepEqual(sequence, ['save', 'release']);
  assert.equal(session.state.getState().mode, 'view');
});

test('template publication and graph saves share the same revision queue', async (t) => {
  const { session, getServer, setServer } = setup(t);
  await session.edit();
  const snapshot: TemplateSnapshot = {
    id: 'custom',
    revision: 1,
    label: 'Custom',
    category: 'Metadata',
    icon: 'metadata',
    color: 'blue',
    profile: 'urn:custom',
    shape: 'urn:custom',
    profile_ttl: '',
    fields: [],
    kind: 'group',
    required: [],
    defaults: {},
  };
  mock.method(projectApi, 'publish', async (_id: string, _token: string, revision: number) => {
    assert.equal(revision, 2);
    setServer({ ...getServer(), revision: 3 });
    return { template: snapshot, revision: 3 };
  });
  session.graph.getState().rename('Before template');
  await session.publish(snapshot);
  session.graph.getState().rename('After template');
  await session.save();
  assert.equal(getServer().revision, 4);
  assert.equal(getServer().name, 'After template');
});

test('an old local recovery draft is never silently restored over newer server content', async (t) => {
  const { session } = setup(t);
  await session.edit();
  session.state.setState({
    recovery: JSON.stringify({
      version: 1,
      base_revision: 0,
      blueprint: { ...blueprint, name: 'Old draft' },
    }),
  });
  session.restore();
  assert.equal(session.graph.getState().name, project.name);
  assert.match(session.state.getState().error, /older server version/);
});

test('discard reloads the server even when only the local draft changed', async (t) => {
  const { session } = setup(t);
  await session.edit();
  session.graph.getState().rename('Discard this');
  await session.discard();
  assert.equal(session.graph.getState().name, project.name);
  assert.equal(session.state.getState().dirty, false);
});

test('validation failures preserve editing so an unfinished project name can be repaired', async (t) => {
  const { session } = setup(t);
  await session.edit();
  mock.method(projectApi, 'save', async () => {
    throw new ApiError(422, 'invalid_name', 'Enter a project name');
  });
  session.graph.getState().rename('');
  await assert.rejects(session.save(), /Enter a project name/);
  assert.equal(session.state.getState().mode, 'editing');
  session.graph.getState().rename('Repaired');
  assert.equal(session.graph.getState().name, 'Repaired');
});

test('finishing freezes content changes while the final save is pending', async (t) => {
  const { session, setServer } = setup(t);
  await session.edit();
  let release: (() => void) | undefined;
  mock.method(
    projectApi,
    'save',
    async (_id: string, _token: string, revision: number, content: Blueprint) => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      const saved = { ...project, blueprint: content, name: content.name, revision: revision + 1 };
      setServer(saved);
      return saved;
    },
  );
  session.graph.getState().rename('Final version');
  const pending = session.finish();
  await new Promise<void>((resolve) => setImmediate(resolve));
  session.graph.getState().rename('Too late');
  assert.equal(session.graph.getState().name, 'Final version');
  release!();
  await pending;
  assert.equal(session.state.getState().dirty, false);
  assert.equal(session.graph.getState().name, 'Final version');
});
