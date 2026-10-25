import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { ChevronDown, Menu, LogOut, UserRound, Settings } from 'lucide-react';
import type { User } from '../projects/types';
import '../styles/shell.css';

export type NavigationDestination = 'projects' | 'templates' | 'profile' | 'about';

type HeaderProps = {
  onNavigate: (destination: NavigationDestination) => void;
  onValidate: () => void;
  user: User;
  inProject: boolean;
  onAccount: () => void;
  onLogout: () => void;
  onAdmin: () => void;
};

/** Shared viewport shell; feature views own their content and data providers. */
export function AppShell({ header, children }: { header: ReactNode; children: ReactNode }) {
  return (
    <div className="app-shell">
      {header}
      <div className="app-content">{children}</div>
    </div>
  );
}

export function GlobalHeader({
  onNavigate,
  onValidate,
  user,
  inProject,
  onAccount,
  onLogout,
  onAdmin,
}: HeaderProps) {
  const [navigationOpen, setNavigationOpen] = useState(false);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  return (
    <header
      className="global-header"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setNavigationOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && navigationOpen) {
          setNavigationOpen(false);
          menuTrigger.current?.focus();
          event.stopPropagation();
        }
      }}
    >
      <div className="brand">
        <span className="brand-logo">
          <DatabaseIcon />
        </span>
        <strong>FAIR Data Design Suite</strong>
      </div>
      <button
        ref={menuTrigger}
        className="navigation-toggle"
        aria-label="Application menu"
        aria-expanded={navigationOpen}
        aria-controls="application-navigation"
        onClick={() => setNavigationOpen((open) => !open)}
      >
        <Menu size={18} /> Menu
      </button>
      <nav
        id="application-navigation"
        className={`global-nav ${navigationOpen ? 'navigation-open' : ''}`}
        aria-label="Application navigation"
        onClick={() => setNavigationOpen(false)}
      >
        <button
          aria-current={!inProject ? 'page' : undefined}
          onClick={() => onNavigate('projects')}
        >
          Projects
        </button>
        <button disabled={!inProject} onClick={() => onNavigate('templates')}>
          Templates
        </button>
        <button disabled={!inProject} onClick={() => onNavigate('profile')}>
          Metadata Profiles (MPS)
        </button>
        <button disabled={!inProject} onClick={() => onValidate()}>
          Validation
        </button>
        <button disabled={!inProject} onClick={() => onNavigate('about')}>
          Help <ChevronDown size={13} />
        </button>
      </nav>
      <div className="global-right">
        <div className="user-avatar" aria-hidden="true">
          {user.display_name
            .split(/\s+/)
            .map((part) => part[0])
            .slice(0, 2)
            .join('')
            .toUpperCase()}
        </div>
        <span className="user-name">{user.display_name}</span>
        {user.is_admin && (
          <button className="top-icon" onClick={onAdmin} aria-label="Administration">
            <Settings size={18} />
          </button>
        )}
        <button className="top-icon" onClick={onAccount} aria-label="Your account">
          <UserRound size={18} />
        </button>
        <button className="top-icon" onClick={onLogout} aria-label="Sign out">
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
function DatabaseIcon() {
  return (
    <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <ellipse cx="16" cy="7" rx="11" ry="4.6" stroke="currentColor" strokeWidth="2.4" />
      <path
        d="M5 7v8c0 2.6 5 4.7 11 4.7s11-2.1 11-4.7V7M5 15v9c0 2.6 5 4.5 11 4.5S27 26.6 27 24v-9"
        stroke="currentColor"
        strokeWidth="2.4"
      />
      <path d="M5 15c0 2.5 5 4.5 11 4.5s11-2 11-4.5" stroke="currentColor" strokeWidth="2.4" />
    </svg>
  );
}
