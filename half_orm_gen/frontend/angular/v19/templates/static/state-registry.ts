const _fns: Array<() => void> = [];
const _keyFns = new Map<string, () => void>();
export function registerClear(fn: () => void): void { _fns.push(fn); }
export function registerClearForKey(key: string, fn: () => void): void { _keyFns.set(key, fn); }
export function clearAllStates(): void { _fns.forEach(fn => fn()); }
export function clearStateForKey(key: string): void { _keyFns.get(key)?.(); }
