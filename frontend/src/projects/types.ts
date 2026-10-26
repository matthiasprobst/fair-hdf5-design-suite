import type { Blueprint } from '../types';

export type Role = 'owner' | 'editor' | 'viewer';
export interface User {
  id: string;
  username: string;
  display_name: string;
  is_admin: boolean;
  active: boolean;
  must_change_password: boolean;
}
export interface PasswordPolicy {
  min_length: number;
  max_length: number;
}
export interface Session {
  user: User | null;
  csrf_token: string;
  password_policy: PasswordPolicy;
}
export interface ProjectSummary {
  example_id?: string | null;
  id: string;
  name: string;
  description: string;
  owner_id: string;
  owner_name: string;
  role: Role;
  shared: boolean;
  revision: number;
  created_at: number;
  updated_at: number;
}
export interface EditLock {
  user_id: string;
  display_name: string;
  expires_at: number;
}
export interface Project extends ProjectSummary {
  blueprint: Blueprint;
  edit_lock: EditLock | null;
}
export interface Member {
  id: string;
  username: string;
  display_name: string;
  role: Role;
}
