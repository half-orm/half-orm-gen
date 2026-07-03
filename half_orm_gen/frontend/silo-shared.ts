/**
 * Framework-agnostic ResourceSilo logic, shared between the Angular and
 * Svelte generated frontends. Pure functions only — no signals/runes,
 * no HTTP client, no framework dependency.
 */

export type Row = Record<string, unknown>;

export type DynamicRoleEntry = {
  ids: string[];
  verbs: string[];
  put_in?: string[];
  put_out?: string[];
};

export type DynamicRoles = Record<string, DynamicRoleEntry>;

/** Build a PK extractor from a resource's pk_fields. */
export function makePkExtractor(pkFields: string[]): ((item: Row) => string) | null {
  if (pkFields.length === 1) {
    const pk = pkFields[0];
    return (item) => String(item[pk]);
  }
  if (pkFields.length > 1) {
    return (item) => pkFields.map(f => `${f}:${item[f]}`).join('::');
  }
  return null;
}

/** Decode a composite id (built by makePkExtractor) back to field→value pairs. */
export function parseCompositePk(id: string): Row {
  const params: Row = {};
  for (const part of id.split('::')) {
    const colon = part.indexOf(':');
    if (colon > 0) params[part.slice(0, colon)] = part.slice(colon + 1);
  }
  return params;
}

/** Build a list URL with `ho_col_*` filters from a params object. */
export function buildListUrl(baseUrl: string, params: Row): string {
  const filtered = Object.fromEntries(
    Object.entries(params)
      .filter(([, v]) => v != null && (typeof v !== 'string' || v !== ''))
      .map(([k, v]) => [`ho_col_${k}`, String(v)])
  );
  const qs = new URLSearchParams(filtered).toString();
  return qs ? `${baseUrl}?${qs}` : baseUrl;
}

/**
 * Merge dynamic_roles freshly resolved for a single refreshed row into the
 * existing dynamic_roles state, without discarding entries for other rows.
 *
 * The single-row refresh only tells us about `refreshedId`: for each role,
 * we drop `refreshedId` from the previously known ids, then re-add it only
 * to the roles it currently qualifies for per `incoming`. Ids belonging to
 * other rows are left untouched.
 */
export function mergeDynamicRoles(
  current: DynamicRoles,
  incoming: DynamicRoles,
  refreshedId: string,
): DynamicRoles {
  const merged: DynamicRoles = {};
  for (const [role, rd] of Object.entries(current)) {
    const ids = rd.ids.filter(x => x !== refreshedId);
    if (ids.length) merged[role] = { ...rd, ids };
  }
  for (const [role, rd] of Object.entries(incoming)) {
    const prevIds = merged[role]?.ids ?? [];
    merged[role] = { ...rd, ids: [...new Set([...prevIds, ...rd.ids])] };
  }
  return merged;
}
