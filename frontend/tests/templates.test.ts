import test from 'node:test';
import assert from 'node:assert/strict';
import { createEditorStore } from '../src/editor/store';
import { parseBlueprint } from '../src/editor/blueprint';
import { toBlueprint } from '../src/editor/adapters';
import {
  parseCatalog,
  parseProfileAnalysis,
  parseTemplate,
  parseValidation,
} from '../src/lib/contracts';
import { buildTemplateDraft } from '../src/library/draft';
import type { ProfileField, TemplateSnapshot } from '../src/types';

const reference: ProfileField = {
  id: 'participant',
  key: 'participant',
  predicate: 'urn:participant',
  label: 'Participant',
  datatype: 'IRI',
  required: false,
  kind: 'reference',
  targetShape: 'urn:person',
};
function snapshot(patch: Partial<TemplateSnapshot> = {}): TemplateSnapshot {
  return {
    id: 'project',
    revision: 1,
    label: 'Project',
    category: 'Metadata',
    kind: 'group',
    color: 'blue',
    icon: 'metadata',
    profile: 'urn:project',
    shape: 'urn:project',
    profile_ttl: '<urn:project> a <urn:shape>.',
    required: [],
    defaults: { path: '/project', tags: ['one', 'two'] },
    fields: [],
    ...patch,
  };
}
function editor() {
  const store = createEditorStore();
  store.getState().setCapabilities({
    max_nodes: 10,
    max_edges: 10,
    max_upload_bytes: 100,
    shacl_engine: 'pyshacl',
  });
  const person = snapshot({ id: 'person', shape: 'urn:person', defaults: { path: '/person' } });
  store.getState().setCatalog({
    project: snapshot({ fields: [reference], related_templates: { 'urn:person': person } }),
  });
  store.getState().addNode('project', 0, 0);
  return store;
}

test('linked node and semantic edge are published in one state change', () => {
  const store = editor();
  const source = store.getState().nodes[0].id;
  const before = store.getState().semanticRevision;
  let notifications = 0;
  const unsubscribe = store.subscribe((state) => {
    notifications++;
    assert.equal(state.nodes.length, 2);
    assert.equal(state.edges.length, 1);
    assert.equal(state.edges[0].target, state.nodes[1].id);
  });
  store.getState().createLinkedNode(source, reference);
  unsubscribe();
  assert.equal(notifications, 1);
  assert.equal(store.getState().semanticRevision, before + 1);
  const unchanged = store.getState();
  store.getState().linkNode(source, reference, unchanged.nodes[1].id);
  store.getState().linkNode('missing', reference, unchanged.nodes[1].id);
  assert.equal(store.getState(), unchanged);
});

test('adding and duplicating nodes isolates repeatable defaults and snapshots', () => {
  const store = editor();
  store.getState().duplicateNode(store.getState().nodes[0].id);
  const [first, second] = store.getState().nodes;
  (first.data.config.tags as string[]).push('edited');
  assert.deepEqual(second.data.config.tags, ['one', 'two']);
  assert.deepEqual(store.getState().catalog.project.defaults.tags, ['one', 'two']);
  const exported = toBlueprint(store.getState());
  (exported.nodes[0].config.tags as string[]).push('export-only');
  assert.equal((first.data.config.tags as string[]).includes('export-only'), false);
});

test('catalog publication preserves existing node revisions; upgrade remaps semantic field IDs', () => {
  const store = editor();
  const source = store.getState().nodes[0].id;
  store.getState().createLinkedNode(source, reference);
  const next = snapshot({ revision: 2, fields: [{ ...reference, id: 'new-participant' }] });
  store.getState().publishTemplate(next, store.getState().catalog.project);
  assert.equal(store.getState().nodes[0].data.template?.revision, 1);
  assert.equal(store.getState().catalog.project.initial?.revision, 1);
  store.getState().upgradeNode(source, next);
  assert.equal(store.getState().nodes[0].data.template?.revision, 2);
  assert.equal(store.getState().edges[0].data?.field_id, 'new-participant');
  const exported = toBlueprint(store.getState());
  assert.deepEqual(parseBlueprint(JSON.parse(JSON.stringify(exported)), {}), exported);
});

test('template drafts preserve repeated defaults and exclude reference attributes', () => {
  const previous = snapshot({
    defaults: { path: '/project', tags: ['one', 'two'], participant: 'old' },
  });
  const draft = buildTemplateDraft(
    {
      mode: 'turtle',
      label: 'Project',
      category: 'Metadata',
      kind: 'group',
      path: '/project',
      dtype: 'float64',
      dimensions: '0',
      color: 'blue',
      icon: 'metadata',
      shape: 'urn:project',
      ttl: previous.profile_ttl,
      sourceUri: '',
      documents: {},
      fields: [
        reference,
        {
          key: 'tags',
          label: 'Tags',
          predicate: 'urn:tags',
          datatype: 'string',
          required: false,
          multiple: true,
        },
      ],
    },
    previous,
  );
  assert.deepEqual(draft.defaults?.tags, ['one', 'two']);
  assert.equal(draft.defaults?.participant, undefined);
  (draft.defaults?.tags as string[]).push('draft-only');
  assert.deepEqual(previous.defaults.tags, ['one', 'two']);
});

test('API contracts reject malformed published snapshots and preserve legacy catalog entries', () => {
  assert.throws(() => parseTemplate({ ...snapshot(), revision: '1' }), /Invalid template/);
  assert.throws(
    () =>
      parseCatalog({
        catalog: { project: { ...snapshot(), fields: [{}] } },
        profile_source: 'local',
      }),
    /Invalid catalog/,
  );
  assert.throws(
    () =>
      parseProfileAnalysis({ documents: {}, shapes: [{ shape: 'urn:project', supported: true }] }),
    /Invalid profile analysis/,
  );
  assert.throws(() => parseValidation({ conforms: true, issues: [] }), /Invalid validation/);
  const result = parseCatalog({
    catalog: { project: snapshot({ revision: 2 }) },
    legacy_catalog: { project: snapshot() },
    profile_source: 'local',
  });
  assert.equal(result.catalog.project.initial?.revision, 1);
});

test('import accepts homogeneous repeatable values and rejects mixed or nested metadata', () => {
  const store = editor();
  const blueprint = toBlueprint(store.getState());
  const imported = parseBlueprint(blueprint, {});
  assert.deepEqual(imported.nodes[0].config.tags, ['one', 'two']);
  (imported.nodes[0].config.tags as string[]).push('import-only');
  assert.deepEqual(blueprint.nodes[0].config.tags, ['one', 'two']);
  for (const tags of [['text', 1], [['nested']]]) {
    const broken = {
      ...blueprint,
      nodes: [{ ...blueprint.nodes[0], config: { ...blueprint.nodes[0].config, tags } }],
    };
    assert.throws(() => parseBlueprint(broken, {}), /unsupported metadata/);
  }
});
