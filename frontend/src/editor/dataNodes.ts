import type { CatalogItem, Config } from '../types';

export const CSV_SOURCE = 'csv_source';
export const csvSource: CatalogItem = {
  label: 'CSV Source',
  category: 'Data inputs',
  icon: 'csv_source',
  profile: '',
  kind: null,
  color: 'green',
  required: [],
  defaults: {
    delimiter: ',',
    decimal_separator: '.',
    has_header: true,
    filename: '',
    columns: [],
  },
};

export function sourceConfig(config: Config): Config {
  const value = { ...structuredClone(csvSource.defaults), ...config };
  if (
    Object.keys(config).some((key) => !(key in csvSource.defaults) && key !== 'example_file') ||
    typeof value.delimiter !== 'string' ||
    ![',', ';', '\t'].includes(value.delimiter) ||
    typeof value.decimal_separator !== 'string' ||
    !['.', ','].includes(value.decimal_separator) ||
    value.delimiter === value.decimal_separator ||
    typeof value.has_header !== 'boolean' ||
    typeof value.filename !== 'string' ||
    value.filename.length > 512 ||
    value.filename.includes('\0') ||
    !Array.isArray(value.columns) ||
    value.columns.some((c) => typeof c !== 'string' || c.includes('\0')) ||
    (value.example_file !== undefined && value.example_file !== 'measurements.csv')
  )
    throw new Error('Invalid CSV source settings or headers.');
  return value;
}
