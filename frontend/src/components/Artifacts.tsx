import {
  ChevronDown,
  Check,
  ChevronRight,
  CircleAlert,
  Database,
  Download,
  Eye,
  FileCheck2,
  FileCode2,
  GitBranch,
  Play,
  RefreshCcw,
  ShieldCheck,
} from 'lucide-react';
import type { ArtifactStatus } from '../editor/artifacts';
import type { Preview, ValidationResult } from '../types';

type Props = {
  onClose: () => void;
  previewStatus: ArtifactStatus;
  validationStatus: ArtifactStatus;
  preview: Preview | null;
  validation: ValidationResult | null;
  busy: string;
  onShaclPreview: () => void;
  onShaclDownload: () => void;
  onMetadataDownload: () => void;
  onStructure: () => void;
  onHdf5Download: () => void;
  onDataDownload: () => void;
  dataIssues: string[];
  dataError: string;
  dataBuilding: boolean;
  onValidation: () => void;
  onReport: () => void;
  onRefresh: () => void;
};
export default function Artifacts({
  onClose,
  previewStatus,
  validationStatus,
  preview,
  validation,
  busy,
  onShaclPreview,
  onShaclDownload,
  onMetadataDownload,
  onStructure,
  onHdf5Download,
  onDataDownload,
  dataIssues,
  dataError,
  dataBuilding,
  onValidation,
  onReport,
  onRefresh,
}: Props) {
  const groups = preview?.objects.filter((o) => o.kind === 'group').length;
  const datasets = preview?.objects.filter((o) => o.kind === 'dataset').length;
  const pending = Boolean(busy);
  const previewLabel = {
    idle: 'Pending',
    loading: 'Loading',
    current: 'Ready',
    stale: 'Stale',
    failed: 'Failed',
  }[previewStatus];
  const validationLabel = {
    idle: 'Not run',
    loading: 'Loading',
    current: 'Current',
    stale: 'Stale',
    failed: 'Failed',
  }[validationStatus];
  return (
    <section className="artifacts-container">
      <div className="artifacts-heading">
        <div>
          <strong>Generated Artifacts</strong>
          <span>From your current experiment blueprint</span>
        </div>
        <div className="artifacts-heading-actions">
          <button className="artifacts-refresh" disabled={pending} onClick={onRefresh}>
            <RefreshCcw size={13} /> Refresh
          </button>
          <button
            className="icon-button"
            aria-label="Collapse generated artifacts"
            title="Collapse generated artifacts"
            onClick={onClose}
          >
            <ChevronDown size={17} />
          </button>
        </div>
      </div>
      <div className="artifacts-grid">
        <article className="artifact-card artifact-shacl">
          <div className="artifact-card-header">
            <span className="artifact-icon">
              <GitBranch size={28} />
            </span>
            <div>
              <strong>SHACL Profile</strong>
              <p>RDF constraints generated from attached local profiles and HDF5 mapping.</p>
            </div>
            <span className="artifact-status">
              {previewLabel} {previewStatus === 'current' && <Check size={12} />}
            </span>
          </div>
          <div className="artifact-stats">
            <span>
              <strong>{preview?.profiles ?? '—'}</strong>
              <small>profiled objects</small>
            </span>
            <span>
              <strong>{preview?.node_count ?? '—'}</strong>
              <small>building blocks</small>
            </span>
            <span>
              <strong>{preview?.edge_count ?? '—'}</strong>
              <small>connections</small>
            </span>
          </div>
          <div className="artifact-actions">
            <button disabled={pending} onClick={onShaclPreview}>
              <Eye size={14} /> Preview
            </button>
            <button disabled={pending} onClick={onShaclDownload}>
              <Download size={14} /> Download .ttl
            </button>
            <button
              disabled={pending}
              onClick={onMetadataDownload}
              title="Download declared DCAT/PROV data-node metadata"
            >
              <Download size={14} /> Metadata .ttl
            </button>
          </div>
        </article>
        <article className="artifact-card artifact-hdf5">
          <div className="artifact-card-header">
            <span className="artifact-icon">
              <Database size={28} />
            </span>
            <div>
              <strong>HDF5 Template</strong>
              <p>File hierarchy, metadata, and datasets. Build a populated file from CSV inputs.</p>
            </div>
            <span className="artifact-status">
              {previewLabel} {previewStatus === 'current' && <Check size={12} />}
            </span>
          </div>
          <div className="artifact-stats">
            <span>
              <strong>{groups ?? '—'}</strong>
              <small>groups</small>
            </span>
            <span>
              <strong>{datasets ?? '—'}</strong>
              <small>datasets</small>
            </span>
            <span>
              <strong>{preview?.profiles ?? '—'}</strong>
              <small>mapped objects</small>
            </span>
          </div>
          <div className="artifact-actions">
            <button disabled={pending} onClick={onStructure}>
              <GitBranch size={14} /> Preview structure
            </button>
            <button disabled={pending} onClick={onHdf5Download}>
              <Download size={14} /> Download template .h5
            </button>
            <button
              disabled={pending || dataBuilding || dataIssues.length > 0}
              onClick={onDataDownload}
            >
              <Download size={14} />
              {dataBuilding ? 'Building HDF5…' : 'Build HDF5 with data'}
            </button>
          </div>
          <div className="artifact-data-export">
            {dataIssues.length ? (
              <p>
                {dataIssues.slice(0, 3).join(' ')}
                {dataIssues.length > 3 ? ` (+${dataIssues.length - 3} more)` : ''}
              </p>
            ) : (
              <p>Every dataset has a source. Values are checked when building.</p>
            )}
            {dataError && (
              <p className="form-error" role="alert">
                {dataError}
              </p>
            )}
          </div>
        </article>
        <article className="artifact-card artifact-validation">
          <div className="artifact-card-header">
            <span className="artifact-icon">
              <ShieldCheck size={28} />
            </span>
            <div>
              <strong>Validation Report</strong>
              <p>Structural HDF5 checks and RDF/SHACL metadata constraints.</p>
            </div>
            <span
              className={`artifact-status ${validation && !validation.conforms ? 'artifact-warning' : ''}`}
            >
              {validation ? (validation.conforms ? 'Passed' : 'Issues') : validationLabel}{' '}
              {validation?.conforms ? (
                <Check size={12} />
              ) : validation ? (
                <CircleAlert size={12} />
              ) : (
                <ChevronRight size={12} />
              )}
            </span>
          </div>
          <div className="artifact-stats">
            <span>
              <strong>{validation?.issue_count ?? '—'}</strong>
              <small>issues</small>
            </span>
            <span>
              <strong>—</strong>
              <small>warnings</small>
            </span>
            <span>
              <strong>{validation?.checks ?? '—'}</strong>
              <small>checks</small>
            </span>
          </div>
          <div className="artifact-actions">
            <button disabled={pending} onClick={onValidation}>
              <Play size={14} /> Run validation
            </button>
            <button disabled={!validation} onClick={onReport}>
              {validation ? <FileCheck2 size={14} /> : <FileCode2 size={14} />} View report
            </button>
          </div>
        </article>
      </div>
    </section>
  );
}
