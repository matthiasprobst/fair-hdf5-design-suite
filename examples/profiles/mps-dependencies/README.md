# Pinned MPS dependencies

These Turtle documents were downloaded unchanged with `Accept: text/turtle`.
The source profiles declare CC0-1.0 licensing.

- `organization.ttl`: https://w3id.org/nfdi4ing/profiles/b836ad06-e1d0-4287-a182-66de74e98eee/
- `person.ttl`: https://w3id.org/nfdi4ing/profiles/e18a558c-03a2-4a89-9cfb-656aad6f6644/1767883664018/

They are the dependencies of an original MPS Research Project profile that
references these documents with `owl:imports`. The checked-in
`../research_project.ttl` bundles the Person and Organization shapes directly
for offline use. The Person document also imports Organization. The
organization URI is unversioned; these local bytes pin the reference profile
independently of future MPS changes.

For offline import of the original profile, supply each file under its full URI
using **Supply a dependency file**, then analyze it. The app stores content
hashes and embeds the dependency bundle in saved template snapshots.
