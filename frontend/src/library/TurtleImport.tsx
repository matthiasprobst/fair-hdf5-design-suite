import type { LibraryEditorModel } from './useLibraryEditor';

export function TurtleImport({ editor }: { editor: LibraryEditorModel }) {
  const {
    busy,
    setError,
    setTtl,
    setSourceUri,
    setDocuments,
    setAnalyzed,
    setAnalysis,
    ttl,
    sourceUri,
    dependencyUri,
    setDependencyUri,
    documents,
    analyze,
    analysis,
    shape,
    setShape,
    setFields,
  } = editor;
  return (
    <section>
      <label>
        Import .ttl file
        <input
          type="file"
          accept=".ttl,text/turtle"
          disabled={busy}
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (file.size > 1_000_000) {
              setError('Profile limit is 1 MB.');
              return;
            }
            try {
              setTtl(await file.text());
              setSourceUri('');
              setDocuments({});
              setAnalyzed(false);
              setAnalysis(null);
            } catch {
              setError('Cannot read this file.');
            }
          }}
        />
      </label>
      <label>
        Turtle source
        <textarea
          className="library-turtle"
          value={ttl}
          onChange={(e) => {
            setTtl(e.target.value);
            setAnalyzed(false);
            setAnalysis(null);
          }}
          spellCheck={false}
        />
      </label>
      <label>
        Source document URI (optional)
        <input
          value={sourceUri}
          onChange={(e) => {
            setSourceUri(e.target.value);
            setAnalyzed(false);
          }}
        />
      </label>
      <details>
        <summary>Supply a dependency file</summary>
        <label>
          Imported document URI
          <input value={dependencyUri} onChange={(e) => setDependencyUri(e.target.value)} />
        </label>
        <label>
          Dependency Turtle
          <input
            type="file"
            accept=".ttl,text/turtle"
            disabled={!dependencyUri.trim()}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              if (file.size > 1_000_000) {
                setError('Dependency limit is 1 MB.');
                return;
              }
              try {
                const content = await file.text();
                setDocuments((d) => ({
                  ...d,
                  [dependencyUri]: { ttl: content, resolved_url: dependencyUri },
                }));
                setAnalyzed(false);
              } catch {
                setError('Cannot read dependency file.');
              }
            }}
          />
        </label>
      </details>
      {Object.entries(documents).map(([uri, doc]) => (
        <p className="muted-small" key={uri}>
          Pinned: {uri}
          {doc.resolved_url && doc.resolved_url !== uri
            ? ` (fetched from ${doc.resolved_url})`
            : ''}{' '}
          {doc.hash?.slice(0, 12)}
        </p>
      ))}
      <button onClick={() => void analyze()} disabled={busy || !ttl.trim()}>
        Analyze profile
      </button>
      {analysis && (
        <div className="library-analysis">
          {analysis.shapes.map((s) => (
            <div key={s.shape}>
              <label>
                <input
                  type="radio"
                  name="profile-shape"
                  checked={shape === s.shape && s.supported}
                  disabled={!s.supported}
                  onChange={() => {
                    setShape(s.shape);
                    setFields(s.fields || []);
                    setAnalyzed(true);
                  }}
                />
                {s.label}
              </label>
              {s.error && <p role="status">{s.error}</p>}
            </div>
          ))}
        </div>
      )}
      {analysis && analysis.unbundled_imports && analysis.unbundled_imports.length > 0 && (
        <p className="muted-small" role="status">
          Imports without a referenced SHACL shape were not downloaded:{' '}
          {analysis.unbundled_imports.join(', ')}. Supply a Turtle dependency file if its vocabulary
          data is needed for validation.
        </p>
      )}
      <p className="muted-small">
        Referenced profiles are pinned with this template. Participants and affiliations become
        linked nodes; repeated values retain their original cardinality.
      </p>
    </section>
  );
}
