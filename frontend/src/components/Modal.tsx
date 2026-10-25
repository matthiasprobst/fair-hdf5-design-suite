import { useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  ClipboardCopy,
  FileCode2,
  Folder,
  FolderTree,
  ShieldCheck,
  X,
} from 'lucide-react';
import type { Preview, ValidationResult } from '../types';
export type Dialog =
  | 'structure'
  | 'shacl'
  | 'validation'
  | 'about'
  | 'templates'
  | 'projects'
  | 'share'
  | 'profile'
  | null;
type Props = {
  dialog: Dialog;
  onClose: () => void;
  preview: Preview | null;
  ttl: string;
  validation: ValidationResult | null;
  name: string;
  onNotice: (s: string) => void;
};
export default function Modal({
  dialog,
  onClose,
  preview,
  ttl,
  validation,
  name,
  onNotice,
}: Props) {
  useEffect(() => {
    if (!dialog) return;
    const fn = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [dialog, onClose]);
  if (!dialog) return null;
  const titles: Record<Exclude<Dialog, null>, string> = {
    structure: 'Target HDF5 structure',
    shacl: 'Generated SHACL Turtle',
    validation: 'Validation report',
    about: 'About the FAIR Data Design Suite',
    templates: 'Reusable building blocks',
    projects: 'Current project',
    share: 'Share your experiment blueprint',
    profile: 'Metadata Profile Service',
  };
  const pathTree = preview?.objects || [];
  const treeItems = new Map<
    string,
    { kind: 'group' | 'dataset'; name: string; label: string; explicit: boolean }
  >();
  pathTree.forEach((obj) => {
    const parts = obj.path.split('/').filter(Boolean);
    parts.forEach((_, i) => {
      const p = '/' + parts.slice(0, i + 1).join('/');
      if (!treeItems.has(p))
        treeItems.set(p, {
          kind: i === parts.length - 1 ? obj.kind : 'group',
          name: parts[i],
          label: i === parts.length - 1 ? obj.label : 'Implicit parent',
          explicit: i === parts.length - 1,
        });
    });
  });
  return (
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="presentation"
    >
      <section className="modal-window" role="dialog" aria-modal="true" aria-label={titles[dialog]}>
        <header className="modal-head">
          <div>
            <span className="modal-kicker">FAIR DATA DESIGN SUITE</span>
            <h2>{titles[dialog]}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            <X size={19} />
          </button>
        </header>
        <div className="modal-content">
          {dialog === 'structure' && (
            <>
              <p>
                Physical hierarchy specified by <strong>{name}</strong>. Parent groups not
                explicitly configured are generated as needed. Numerical datasets are empty in the
                template.
              </p>
              <div className="structure-tree">
                <div className="structure-entry root-entry">
                  <FolderTree size={17} /> experiment-template.h5
                </div>
                {[...treeItems.entries()]
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([path, obj]) => (
                    <div
                      key={path}
                      style={{ paddingLeft: 18 + path.split('/').filter(Boolean).length * 18 }}
                      className={`structure-entry ${obj.explicit ? '' : 'implicit'}`}
                    >
                      <span className="structure-guide" />
                      {obj.kind === 'group' ? <Folder size={15} /> : <FileCode2 size={15} />}
                      <span>{obj.name}</span>
                      <small>
                        {obj.kind}
                        {!obj.explicit ? ' · implicit' : ''}
                      </small>
                    </div>
                  ))}
              </div>
              <div className="dialog-note">
                HDF5 ancestry is derived from target paths, not the connections on the visual
                workflow canvas.
              </div>
            </>
          )}
          {dialog === 'shacl' && (
            <>
              <p>
                The generated Turtle describes rules for an{' '}
                <strong>RDF projection of the HDF5 file</strong>. A separate HDF5 validator checks
                physical object existence, types, and numerical shapes.
              </p>
              <pre className="code-preview">{ttl || 'No SHACL has been generated yet.'}</pre>
              <button
                className="dialog-copy"
                onClick={() => {
                  void navigator.clipboard
                    .writeText(ttl)
                    .then(() => onNotice('Turtle source copied.'))
                    .catch(() => onNotice('Unable to access clipboard.'));
                }}
              >
                <ClipboardCopy size={14} /> Copy Turtle
              </button>
            </>
          )}
          {dialog === 'validation' && (
            <>
              {!validation ? (
                <div className="empty-report">
                  <ShieldCheck size={42} />
                  <p>Run validation to see the result.</p>
                </div>
              ) : (
                <>
                  <div className={`validation-summary ${validation.conforms ? 'pass' : 'fail'}`}>
                    {validation.conforms ? <CheckCircle2 size={24} /> : <AlertTriangle size={24} />}
                    <div>
                      <strong>
                        {validation.conforms
                          ? 'All modeled checks passed'
                          : 'Conformance issues found'}
                      </strong>
                      <p>
                        {validation.checks} checks · {validation.issue_count} issues ·{' '}
                        {validation.shacl_engine}
                      </p>
                    </div>
                  </div>
                  <div className="report-subtitle">Detailed findings</div>
                  {validation.issues.length ? (
                    <div className="issues-list">
                      {validation.issues.map((issue, i) => (
                        <article className="issue-item" key={`${issue.path}_${i}`}>
                          <span className="issue-layer">{issue.layer}</span>
                          <strong>{issue.message}</strong>
                          <code>{issue.path}</code>
                          <small>Rule: {issue.rule}</small>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="no-issues">
                      <CheckCircle2 size={17} /> No violations among the checks performed.
                    </p>
                  )}
                  <div className="dialog-note">{validation.note}</div>
                </>
              )}
            </>
          )}
          {dialog === 'about' && (
            <>
              <p>
                This research demonstrator connects a virtual experiment model with explicit HDF5
                target paths, local illustrative metadata requirements, SHACL generation, and
                Python-based HDF5 creation/validation.
              </p>
              <p>
                MPS Turtle profiles can be imported with pinned dependencies and linked person and
                organization nodes.
              </p>
              <div className="dialog-note">
                <CircleHelp size={16} /> SHACL conformance does not demonstrate scientific
                correctness or complete FAIR compliance.
              </div>
            </>
          )}
          {dialog === 'templates' && (
            <>
              <p>
                Components in the left building-block library are reusable local templates. Drag a
                sensor, DAQ, group or dataset onto the canvas to create a configured copy.
              </p>
              <p>
                Use Create / import template in the library to create a persistent template or
                import SHACL Turtle. Existing nodes keep their saved revision.
              </p>
            </>
          )}
          {dialog === 'projects' && (
            <>
              <p>
                Active project: <strong>{name}</strong>
              </p>
              <p>
                Your current blueprint is automatically saved in this browser. Download it as JSON
                to transfer it to another computer or preserve a version.
              </p>
            </>
          )}
          {dialog === 'share' && (
            <>
              <p>
                To share a reproducible design, export the <strong>Blueprint JSON</strong> from the
                project menu or export SHACL and an HDF5 template.
              </p>
              <p>
                Multiuser collaboration and cloud sharing are not implemented in this local proof of
                concept.
              </p>
            </>
          )}
          {dialog === 'profile' && (
            <>
              <p>
                Each block uses a <strong>versioned local SHACL profile</strong> stored with the
                design. Required fields generate SHACL constraints on the RDF representation of each
                HDF5 object.
              </p>
              <p>
                Import supported SHACL profiles and their dependencies from Turtle files through the
                library. Direct MPS discovery and synchronization are not connected.
              </p>
              <p>
                <a href="https://profiles.nfdi4ing.de/" target="_blank" rel="noreferrer">
                  Open the NFDI4Ing Metadata Profile Service ↗
                </a>
              </p>
            </>
          )}
        </div>
        <footer className="modal-footer">
          <button onClick={onClose}>Close</button>
        </footer>
      </section>
    </div>
  );
}
