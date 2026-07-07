# AuthService / AuthState reference

> Angular usage in access control: [angular/access-control.md](../angular/access-control.md)  
> Svelte usage in access control: [svelte/access-control.md](../svelte/access-control.md)  
> Consumed by every silo's access members: [resource-silo-reference.md](resource-silo-reference.md)  
> Backend endpoints it calls (`/ho_access`, `/ho_setup`, `/ho_admin/*`, JWT): [../backend/authorization.md](../backend/authorization.md)  
> Local authentication (what your login route must return): [../authentication/local-auth.md](../authentication/local-auth.md)  
> Cross-peer federated sign-in (`peers`, `loginUrlForPeer`, `/auth/delegate`): [../authentication/federation.md](../authentication/federation.md)

---

## One scaffolded singleton, not regenerated

Unlike `ResourceSilo`, the auth service is **scaffolded once and never
overwritten** by `half_orm gen frontend` (see the regenerated-vs-scaffolded
table in [code-organization.md](code-organization.md)):

- Angular: `src/app/core/auth.service.ts` — `@Injectable({ providedIn: 'root' })`, inject with `inject(AuthService)`.
- Svelte: `src/lib/auth.svelte.ts` — a module-level singleton, `export const auth = new AuthState()`; import it directly, no injection.

Because it's scaffolded rather than regenerated, you're free to extend it —
it won't be clobbered on the next `gen frontend`. This page documents the
members it ships with.

Angular exposes reactive members as **signals** (call with `()`); Svelte
exposes them as **runes** (read as plain properties). Methods are called the
same way in both.

---

## Session state

| Member | Angular | Svelte | Description |
|---|---|---|---|
| `token` | `Signal<string \| null>` | `string \| null` (`$state`) | Current JWT, persisted in `sessionStorage['ho_token']`. `null` = anonymous. |
| `userId` | `computed<string \| null>` | `string \| null` (`$derived`) | Decoded `sub` claim from `token`. |
| `userRoles` | `computed<string[]>` | `string[]` (`$derived`) | Decoded `roles` claim from `token` — the *declared* roles, before hierarchy expansion (see [authorization.md](../backend/authorization.md#role-hierarchy-and-inheritance)). |
| `displayName` | `computed<string>` | `string` (`$derived`) | Matches `userId` against `users`; `'anonymous'` if none. |
| `isAdmin` | `computed<boolean>` | `boolean` (`$derived`) | True if `userId` matches a user in `users` with `is_admin`. |
| `users` | `Signal<HoUser[]>` | `HoUser[]` (`$state`) | Cached result of `GET /ho_users` (`{id, name, is_admin}[]`). |
| `hasAdmin` | `Signal<boolean \| null>` | `boolean \| null` (`$state`) | Result of `GET /ho_setup` — `null` until fetched, then whether an admin account already exists. |
| `peers` | `Signal<{id, name, url, frontend_url}[]>` | `{id, name, url, frontend_url}[]` (`$state`) | Trusted peers this project can delegate sign-in to — result of `GET /auth/peers`. `id` is the peer's own `HO_PEER_ID`, the actual lookup key; `name` is display-only; `frontend_url` may be `null` if that peer never set `HO_FRONTEND_URL`. See [federation.md](../authentication/federation.md). |
| `localAuthEnabled` | `Signal<boolean>` | `boolean` (`$state`) | From the same `/auth/peers` response — `false` hides the local email/password form entirely (federation-only peer, `HO_LOCAL_AUTH=none`). |
| `localPeerName` | `Signal<string \| null>` | `string \| null` (`$state`) | This project's own `HO_PEER_NAME` (from `/auth/peers`' `local_name`) — `null` if unset (non-federated project). Labels the local sign-in form ("Sign in on `<localPeerName>`"). |
| `localPeerId` | `Signal<string \| null>` | `string \| null` (`$state`) | This project's own `HO_PEER_ID` (`local_id`) — used by `federationNavUrl` to build cross-site navigation links. |

---

## Access map state

| Member | Angular | Svelte | Description |
|---|---|---|---|
| `access` | `Signal<Record<string, any>>` | `Record<string, any>` (`$state`) | Raw result of `GET /ho_access` for the real (non-simulated) session. |
| `effectiveAccess` | `computed<Record<string, any>>` | — (Angular only) | `simulatedAccess ?? access` — what every silo actually reads. Svelte has no simulation, so silos read `access` directly. |
| `accessVersion` | `Signal<number>` | `number` (`$state`) | Bumped on any full access reload; bump it yourself to force-invalidate derived state elsewhere. |
| `resourceAccessVersion` | `Signal<Record<string, number>>` | `Record<string, number>` (`$state`) | Per-resource counter, bumped when `access_reload` targets one resource. Read `resourceAccessVersion()['schema/table']` in an `effect`/`$effect` to react to just that resource's access changing. |
| `catalog` | `Signal<Partial<Record<string, CatalogEntry>>>` | — (Angular only) | Full access catalog from `GET /ho_admin/catalog`, fetched only for admins. Powers the Admin UI. |

---

## Session methods

| Method | Signature | Description |
|---|---|---|
| `loginWithEmail` | `(email: string, password: string) => Promise<void>` | Calls the app's `POST /auth/login`, then `setToken` with the returned JWT. Your `ho_api/custom/routes.py` login route just needs to return `{token: "..."}` — see [local-auth.md](../authentication/local-auth.md). |
| `signupUser` | `(name: string, email: string, password: string) => Promise<void>` | Same shape, against `POST /auth/signup`. |
| `setToken` | `(jwt: string) => void` | Stores the JWT, clears `fetchedRoutes` and all silo state (`clearAllStates`), exits any active simulation, then re-fetches access/roles/users. Call directly if you already have a token from elsewhere — this is exactly what the `/auth/callback` page does. |
| `logout` | `() => void` | Clears the JWT and all silo state, exits simulation, navigates away from any `f_`-prefixed (filtered) route, re-fetches access/roles. |
| `_fetchPeers` | `() => Promise<void>` | Fetches `GET /auth/peers` into `peers`/`localAuthEnabled`. Called once at bootstrap. |
| `loginUrlForPeer` | `(peerId: string) => string` | Builds the `/auth/login?peer=...&return_to=...` link for a "Sign in via `name`" button — takes the peer's `id`, not its `name` — see [federation-protocol.md](../internals/federation-protocol.md#the-delegation-protocol). |
| `federationNavUrl` | `(peer: {url, frontend_url}) => string` | Builds the sidebar's "Federation" nav link — a delegation-initiating URL on the *target's own* API (not just a plain link to its homepage), so navigating there can land already signed in. See [federation-protocol.md — cross-site navigation](../internals/federation-protocol.md#cross-site-navigation-federationnavurl). |

---

## Live updates

| Member | Signature | Description |
|---|---|---|
| `connectWs` (Angular) / `_connectWs` (Svelte) | `() => void` | Opens the `/ws` WebSocket, reconnects after 2s on close. Called once at app bootstrap (`app.config.ts` / root layout). |
| `wsEvent$` (Angular, `Subject<WsEvent>`) / `lastEvent` (Svelte, `WsEvent \| null` `$state`) | — | Every non-`access_reload` WebSocket message. Every silo subscribes to this, filtering on its own resource key — see [resource-silo-reference.md](resource-silo-reference.md#companion-authserviceauthstate-members). |
| `access_reload` handling | internal | An `access_reload` event is intercepted before reaching `wsEvent$`/`lastEvent` and routed to `_reloadAccess(resource?)` instead — this is how a role/CRUD_ACCESS change made in the Admin UI propagates live to open sessions without a page refresh. |
| `fetchedRoutes` | `Set<string>` | Shared request-dedup cache read by every silo's `list`/`get`/`refresh`. Cleared on login, logout, simulation change, and full/partial access reload. |

---

## Role simulation (Angular only)

No equivalent in Svelte — per [svelte/access-control.md](../svelte/access-control.md), Svelte has no Admin UI and access configuration is managed exclusively through the Angular one.

| Member | Signature | Description |
|---|---|---|
| `simulatedRole` | `Signal<string \| null>` | Role currently being simulated, or `null`. |
| `simulatedAccess` | `Signal<Record<string, any> \| null>` | Access map fetched for `simulatedRole`. |
| `simulateRole` | `(role: string) => Promise<void>` | Fetches `GET /ho_admin/simulate-access?role=<role>`, clears `fetchedRoutes` and silo state so everything re-fetches under the simulated access. |
| `exitSimulation` | `() => void` | Clears simulation state, back to the real `access`. |

---

## Route guards (Angular)

Scaffolded in `src/app/core/`, not part of `AuthService` itself but built directly on its signals:

```typescript
// auth.guard.ts
export function authGuard(): boolean {
  const auth = inject(AuthService);
  if (auth.token()) return true;
  void inject(Router).navigate(['/login']);
  return false;
}

// admin.guard.ts
export async function adminGuard(): Promise<boolean> {
  const auth = inject(AuthService);
  if (auth.token() && auth.users().length === 0) await auth._fetchUsers();
  if (auth.isAdmin()) return true;
  void inject(Router).navigate(['/ho_bo']);
  return false;
}
```

Svelte enforces the equivalent in the `(nav)/+layout.ts`/`+layout.svelte` scaffold rather than a route-guard function — see [code-organization.md](code-organization.md#svelte--directory-structure).
