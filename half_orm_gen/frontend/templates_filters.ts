/**
 * Shared filter validation, normalization, and matching utilities
 * Used by both Angular and Svelte generated components
 */

export type FieldType = 'date' | 'datetime' | 'number' | 'string';

/**
 * Validates a filter value based on field type
 * @param field - Field name
 * @param value - Filter value (may contain operators like >=, >, <=, <)
 *                Supports range syntax: >=2025<2026 for date/datetime
 * @param fieldTypes - Map of field names to their types
 * @returns true if valid, false otherwise
 */
export function isValidFilterValue(
  field: string,
  value: string,
  fieldTypes: Record<string, FieldType>
): boolean {
  const fieldType = fieldTypes[field];
  if (!fieldType) return true;

  // Check for range syntax: >=val1<val2 or >val1<=val2, etc.
  const rangeMatch = value.match(/^(>=|>)(.+?)(<=|<)(.+)$/);
  if (rangeMatch) {
    const [, , operand1, , operand2] = rangeMatch;
    const trimmed1 = operand1.trim();
    const trimmed2 = operand2.trim();

    // Validate both operands
    switch (fieldType) {
      case 'date':
        return isValidDateOperand(trimmed1) && isValidDateOperand(trimmed2);
      case 'datetime':
        return isValidDatetimeOperand(trimmed1) && isValidDatetimeOperand(trimmed2);
      case 'number':
        return !isNaN(Number(trimmed1)) && trimmed1 !== '' &&
               !isNaN(Number(trimmed2)) && trimmed2 !== '';
      default:
        return false;
    }
  }

  // Single operator or no operator
  const match = value.match(/^(>=|>|<=|<)(.*)$/);
  const operand = match ? match[2].trim() : value;

  switch (fieldType) {
    case 'date':
      return isValidDateOperand(operand);
    case 'datetime':
      return isValidDatetimeOperand(operand);
    case 'number':
      return !isNaN(Number(operand)) && operand.trim() !== '';
    default:
      return true;
  }
}

/**
 * Validates a date operand (supports YYYY, YYYY-MM, or YYYY-MM-DD)
 */
function isValidDateOperand(operand: string): boolean {
  return /^\d{4}(-\d{2}(-\d{2})?)?$/.test(operand);
}

/**
 * Validates a datetime operand (supports YYYY, YYYY-MM, YYYY-MM-DD, or full datetime)
 */
function isValidDatetimeOperand(operand: string): boolean {
  return /^\d{4}(-\d{2}(-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?)?)?$/.test(operand);
}

/**
 * Normalizes a filter value for backend compatibility
 * @param field - Field name
 * @param value - Filter value
 * @param fieldTypes - Map of field names to their types
 * @returns Normalized value
 */
export function normalizeFilterValue(
  field: string,
  value: string,
  fieldTypes: Record<string, FieldType>
): string {
  const fieldType = fieldTypes[field];
  if (!fieldType) return value;

  // Check for range syntax: >=val1<val2
  const rangeMatch = value.match(/^(>=|>)(.+?)(<=|<)(.+)$/);
  if (rangeMatch) {
    const [, op1, operand1, op2, operand2] = rangeMatch;
    const trimmed1 = operand1.trim();
    const trimmed2 = operand2.trim();

    if (fieldType === 'date') {
      const normalized1 = normalizeDateOperand(trimmed1);
      const normalized2 = normalizeDateOperand(trimmed2);
      return `${op1}${normalized1}${op2}${normalized2}`;
    }

    if (fieldType === 'datetime') {
      const normalized1 = normalizeDatetimeOperand(trimmed1);
      const normalized2 = normalizeDatetimeOperand(trimmed2);
      return `${op1}${normalized1}${op2}${normalized2}`;
    }

    // For numbers, no normalization needed
    return value;
  }

  // Single operator or no operator
  const match = value.match(/^(>=|>|<=|<)(.*)$/);
  const operator = match ? match[1] : '';
  const operand = match ? match[2].trim() : value;

  if (fieldType === 'datetime') {
    const normalized = normalizeDatetimeOperand(operand);
    return operator + normalized;
  }

  if (fieldType === 'date') {
    const normalized = normalizeDateOperand(operand);
    return operator + normalized;
  }

  return value;
}

/**
 * Normalizes a date operand to YYYY-MM-DD format
 * - YYYY -> YYYY-01-01
 * - YYYY-MM -> YYYY-MM-01
 * - YYYY-MM-DD -> YYYY-MM-DD (unchanged)
 */
function normalizeDateOperand(operand: string): string {
  if (/^\d{4}$/.test(operand)) {
    return `${operand}-01-01`;
  }
  if (/^\d{4}-\d{2}$/.test(operand)) {
    return `${operand}-01`;
  }
  return operand;
}

/**
 * Normalizes a datetime operand to YYYY-MM-DD HH:MM format
 * - YYYY -> YYYY-01-01 00:00
 * - YYYY-MM -> YYYY-MM-01 00:00
 * - YYYY-MM-DD -> YYYY-MM-DD 00:00
 * - YYYY-MM-DDTHH:MM -> YYYY-MM-DD HH:MM (replace T with space)
 */
function normalizeDatetimeOperand(operand: string): string {
  // Replace 'T' with space for backend compatibility
  let normalized = operand.replace('T', ' ');

  if (/^\d{4}$/.test(normalized)) {
    return `${normalized}-01-01 00:00`;
  }
  if (/^\d{4}-\d{2}$/.test(normalized)) {
    return `${normalized}-01 00:00`;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    return `${normalized} 00:00`;
  }

  return normalized;
}

/**
 * Matches an item value against a filter value with operator support
 * @param itemValue - Value from the item to match
 * @param filterValue - Filter value (may contain operators or range syntax)
 * @returns true if matches, false otherwise
 */
export function matchFilter(itemValue: unknown, filterValue: string): boolean {
  if (!filterValue) return true;

  // Detect range syntax: >=val1<val2
  const rangeMatch = filterValue.match(/^(>=|>)(.+?)(<=|<)(.+)$/);
  if (rangeMatch) {
    const [, op1, val1, op2, val2] = rangeMatch;
    const trimmedVal1 = val1.trim();
    const trimmedVal2 = val2.trim();

    // Try numeric comparison first
    const numVal1 = Number(trimmedVal1);
    const numVal2 = Number(trimmedVal2);
    const numItem = Number(itemValue);
    if (!isNaN(numVal1) && !isNaN(numVal2) && !isNaN(numItem)) {
      const check1 = op1 === '>=' ? numItem >= numVal1 : numItem > numVal1;
      const check2 = op2 === '<=' ? numItem <= numVal2 : numItem < numVal2;
      return check1 && check2;
    }

    // Lexicographic comparison (for dates/strings)
    const strItem = String(itemValue ?? '').replace('T', ' ');
    const normalizedVal1 = trimmedVal1.replace('T', ' ');
    const normalizedVal2 = trimmedVal2.replace('T', ' ');
    const check1 = op1 === '>=' ? strItem >= normalizedVal1 : strItem > normalizedVal1;
    const check2 = op2 === '<=' ? strItem <= normalizedVal2 : strItem < normalizedVal2;
    return check1 && check2;
  }

  // Detect single comparison operator
  const match = filterValue.match(/^(>=|>|<=|<)(.*)$/);
  if (match) {
    const [, op, val] = match;
    const trimmedVal = val.trim();

    // Try numeric comparison first
    const numVal = Number(trimmedVal);
    const numItem = Number(itemValue);
    if (!isNaN(numVal) && !isNaN(numItem)) {
      if (op === '>=') return numItem >= numVal;
      if (op === '>') return numItem > numVal;
      if (op === '<=') return numItem <= numVal;
      if (op === '<') return numItem < numVal;
    }

    // Otherwise lexicographic comparison (for dates/strings)
    // Normalize datetime: replace 'T' with space for consistent comparison
    const strItem = String(itemValue ?? '').replace('T', ' ');
    const normalizedVal = trimmedVal.replace('T', ' ');
    if (op === '>=') return strItem >= normalizedVal;
    if (op === '>') return strItem > normalizedVal;
    if (op === '<=') return strItem <= normalizedVal;
    if (op === '<') return strItem < normalizedVal;
  }

  // Contains filter: *text (mirrors the backend's `col:*text` convention)
  if (filterValue.startsWith('*')) {
    const term = filterValue.slice(1);
    if (!term) return true;
    return removeAccents(String(itemValue ?? '').toLowerCase())
      .includes(removeAccents(term.toLowerCase()));
  }

  // Normal text filter (startsWith + unaccent)
  return removeAccents(String(itemValue ?? '').toLowerCase())
    .startsWith(removeAccents(filterValue.toLowerCase()));
}

/**
 * Removes accents from a string for case-insensitive comparison
 * @param s - String to normalize
 * @returns String without accents
 */
export function removeAccents(s: string): string {
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

/**
 * Formats a cell value for display
 * @param v - Value to format
 * @returns Formatted string
 */
export function fmtCell(v: unknown): string {
  if (v == null) return '';
  if (Array.isArray(v)) return `JSON [${v.length}]`;
  if (typeof v === 'object') return 'JSON {…}';
  const s = String(v);
  // Truncate UUIDs
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s)
    ? s.slice(0, 8) + '…' : s;
}

/**
 * Gets the title (tooltip) for a cell
 * @param v - Value to display
 * @returns Title string
 */
export function cellTitle(v: unknown): string {
  if (v == null || typeof v === 'object') return '';
  return String(v);
}

/**
 * Parses URL query parameters to extract filter values
 * @param params - URLSearchParams or Record of query params
 * @param fieldTypes - Map of field names to their types
 * @returns Record of filter field names to values
 */
export function parseFiltersFromUrl(
  params: URLSearchParams | Record<string, string>,
  fieldTypes: Record<string, FieldType>
): Record<string, string> {
  const urlFilters: Record<string, string> = {};

  const entries = params instanceof URLSearchParams
    ? Array.from(params.entries())
    : Object.entries(params);

  entries.forEach(([key, value]) => {
    if (key.startsWith('f_') && typeof value === 'string') {
      const fieldName = key.substring(2);
      const decodedValue = decodeURIComponent(value);

      // Validate before accepting
      if (isValidFilterValue(fieldName, decodedValue, fieldTypes)) {
        urlFilters[fieldName] = decodedValue;
      }
    }
  });

  return urlFilters;
}

/**
 * Encodes filters into URL query parameter format
 * @param filters - Record of filter field names to values
 * @param fieldTypes - Map of field names to their types
 * @returns Record of URL parameter names (f_fieldname) to encoded values
 */
export function encodeFiltersToUrlParams(
  filters: Record<string, string>,
  fieldTypes: Record<string, FieldType>
): Record<string, string> {
  const params: Record<string, string> = {};

  Object.entries(filters).forEach(([field, value]) => {
    if (value && isValidFilterValue(field, value, fieldTypes)) {
      params[`f_${field}`] = encodeURIComponent(value);
    }
  });

  return params;
}
