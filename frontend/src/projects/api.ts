import type { Blueprint, Catalog, TemplateDraft } from '../types';
import { parseCatalog, parseTemplate } from '../lib/contracts';
import { isRecord } from '../lib/validation';
import { jsonRequest, request } from '../lib/http';
import { parseBlueprint } from '../editor/blueprint';
import type { EditLock, Member, Project, ProjectSummary, Session, User } from './types';

function invalid(): never {
  throw new Error('Invalid server response. Please reload and try again.');
}
const strings = (v: Record<string, unknown>, keys: string[]) =>
  keys.every((k) => typeof v[k] === 'string');
function parseUser(v: unknown): User {
  if (
    !isRecord(v) ||
    !strings(v, ['id', 'username', 'display_name']) ||
    !['is_admin', 'active', 'must_change_password'].every((k) => typeof v[k] === 'boolean')
  )
    invalid();
  return v as unknown as User;
}
export function parseSession(v: unknown): Session {
  if (
    !isRecord(v) ||
    typeof v.csrf_token !== 'string' ||
    !isRecord(v.password_policy) ||
    !Number.isInteger(v.password_policy.min_length) ||
    Number(v.password_policy.min_length) < 3 ||
    Number(v.password_policy.min_length) > 128 ||
    v.password_policy.max_length !== 128
  )
    invalid();
  return {
    user: v.user === null ? null : parseUser(v.user),
    csrf_token: v.csrf_token,
    password_policy: {
      min_length: Number(v.password_policy.min_length),
      max_length: v.password_policy.max_length,
    },
  };
}
export function parseSummary(v: unknown): ProjectSummary {
  if (
    !isRecord(v) ||
    !strings(v, ['id', 'name', 'description', 'owner_id', 'owner_name']) ||
    !['owner', 'editor', 'viewer'].includes(String(v.role)) ||
    typeof v.shared !== 'boolean' ||
    !['revision', 'created_at', 'updated_at'].every(
      (k) => typeof v[k] === 'number' && Number.isFinite(v[k]),
    ) ||
    !Number.isInteger(v.revision) ||
    Number(v.revision) < 1
  )
    invalid();
  return v as unknown as ProjectSummary;
}
export function parseLock(v: unknown): EditLock | null {
  if (v === null) return null;
  if (
    !isRecord(v) ||
    !strings(v, ['user_id', 'display_name']) ||
    typeof v.expires_at !== 'number' ||
    !Number.isFinite(v.expires_at)
  )
    invalid();
  return v as unknown as EditLock;
}
function parseProject(v: unknown, catalog: Catalog): Project {
  const summary = parseSummary(v);
  if (!isRecord(v)) invalid();
  return {
    ...summary,
    blueprint: parseBlueprint(v.blueprint, catalog),
    edit_lock: parseLock(v.edit_lock),
  };
}
function parseMembers(v: unknown): Member[] {
  if (!Array.isArray(v)) invalid();
  return v.map((item) => {
    if (
      !isRecord(item) ||
      !strings(item, ['id', 'username', 'display_name']) ||
      !['owner', 'editor', 'viewer'].includes(String(item.role))
    )
      invalid();
    return item as unknown as Member;
  });
}
function password(v: unknown): string {
  if (!isRecord(v) || typeof v.temporary_password !== 'string') invalid();
  return v.temporary_password;
}
const path = (id: string) => `/api/projects/${encodeURIComponent(id)}`;
export const accountApi = {
  session: async () => parseSession(await jsonRequest('/api/auth/session')),
  login: async (username: string, password: string) =>
    parseSession(await jsonRequest('/api/auth/login', 'POST', { username, password })),
  logout: () => jsonRequest('/api/auth/logout', 'POST'),
  changePassword: async (old_password: string, new_password: string) =>
    parseSession(await jsonRequest('/api/auth/password', 'POST', { old_password, new_password })),
  users: async () => {
    const v = await jsonRequest('/api/admin/users');
    if (!Array.isArray(v)) invalid();
    return v.map(parseUser);
  },
  createUser: async (username: string, display_name: string, is_admin: boolean) =>
    password(await jsonRequest('/api/admin/users', 'POST', { username, display_name, is_admin })),
  setActive: (id: string, active: boolean) =>
    jsonRequest(`/api/admin/users/${encodeURIComponent(id)}`, 'PATCH', { active }),
  resetPassword: async (id: string) =>
    password(await jsonRequest(`/api/admin/users/${encodeURIComponent(id)}/password`, 'POST')),
};
export const projectApi = {
  list: async () => {
    const v = await jsonRequest('/api/projects');
    if (!Array.isArray(v)) invalid();
    return v.map(parseSummary);
  },
  create: async (body: {
    name: string;
    description?: string;
    blueprint?: Blueprint;
    source_id?: string;
    import_key?: string;
  }) => parseSummary(await jsonRequest('/api/projects', 'POST', body)),
  get: async (id: string, catalog: Catalog, signal?: AbortSignal) =>
    parseProject(await jsonRequest(path(id), 'GET', undefined, undefined, signal), catalog),
  save: async (
    id: string,
    token: string,
    revision: number,
    blueprint: Blueprint,
    description: string,
    catalog: Catalog,
  ) =>
    parseProject(
      await jsonRequest(
        path(id),
        'PUT',
        { blueprint, description, expected_revision: revision },
        { 'X-Edit-Lease': token },
      ),
      catalog,
    ),
  remove: (id: string) => jsonRequest(path(id), 'DELETE'),
  catalog: async (id: string, signal?: AbortSignal) =>
    parseCatalog(await jsonRequest(`${path(id)}/catalog`, 'GET', undefined, undefined, signal)),
  acquire: async (id: string, editor_id: string) => {
    const v = await jsonRequest(`${path(id)}/edit-lock`, 'POST', { editor_id });
    if (
      !isRecord(v) ||
      typeof v.token !== 'string' ||
      typeof v.expires_at !== 'number' ||
      typeof v.revision !== 'number'
    )
      invalid();
    return { token: v.token, expires_at: v.expires_at, revision: v.revision };
  },
  renew: async (id: string, token: string) => {
    const v = await jsonRequest(`${path(id)}/edit-lock/renew`, 'POST', undefined, {
      'X-Edit-Lease': token,
    });
    if (!isRecord(v) || typeof v.expires_at !== 'number') invalid();
    return v.expires_at;
  },
  lock: async (id: string) => {
    const v = await jsonRequest(`${path(id)}/edit-lock`);
    if (!isRecord(v)) invalid();
    return parseLock(v.edit_lock);
  },
  release: (id: string, token: string, keepalive = false) =>
    request(`${path(id)}/edit-lock`, {
      method: 'DELETE',
      headers: { 'X-Edit-Lease': token },
      keepalive,
    }),
  members: async (id: string) => parseMembers(await jsonRequest(`${path(id)}/members`)),
  member: async (id: string, username: string, role: 'editor' | 'viewer' | null) =>
    parseMembers(await jsonRequest(`${path(id)}/members`, 'PUT', { username, role })),
  publish: async (
    id: string,
    token: string,
    revision: number,
    template: TemplateDraft,
    templateId?: string,
    templateRevision?: number,
    signal?: AbortSignal,
  ) => {
    const v = await jsonRequest(
      `${path(id)}/catalog${templateId ? `/${encodeURIComponent(templateId)}/revisions` : ''}`,
      'POST',
      { template, expected_revision: revision, expected_template_revision: templateRevision },
      { 'X-Edit-Lease': token },
      signal,
    );
    if (!isRecord(v) || typeof v.project_revision !== 'number') invalid();
    return { template: parseTemplate(v), revision: v.project_revision };
  },
};
