export function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}
export function jsonFile(obj: unknown, filename: string): void {
  download(new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' }), filename);
}
