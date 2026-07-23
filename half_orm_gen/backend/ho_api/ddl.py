"""DDL for the "half_orm_meta.api" schema."""

HO_API_DDL = """\
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE SCHEMA IF NOT EXISTS "half_orm_meta.api";

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".resource (
  schemaname text NOT NULL,
  relname    text NOT NULL,
  PRIMARY KEY (schemaname, relname)
);

ALTER TABLE "half_orm_meta.api".resource
  ADD COLUMN IF NOT EXISTS is_association boolean NOT NULL DEFAULT false;
-- True for a pure many-to-many junction table (its PK is exactly its two
-- single-column FKs, each to a different table) — set to an auto-detected
-- default the first time Resource.sync() discovers the resource (see
-- reconcile_catalog), never touched again afterwards so an admin override
-- (POST .../ho_admin/resource_association) survives every later reconcile.

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".role (
  name        text PRIMARY KEY,
  deletable   boolean NOT NULL DEFAULT TRUE,
  parent_name text REFERENCES "half_orm_meta.api".role(name),
  schemaname  text,
  relname     text
);

ALTER TABLE "half_orm_meta.api".role
  ADD COLUMN IF NOT EXISTS schemaname text,
  ADD COLUMN IF NOT EXISTS relname text;
-- Set only for dynamic roles (registered via @ho_api_role on a resource
-- class — half_orm_gen/backend/ho_api/registry.py). NULL means a normal
-- (static) role, valid for every resource. Non-NULL *is* what makes a role
-- "dynamic": it only makes sense — and should only be offered as
-- configurable — in the context of that one resource (e.g. `post_author`
-- has no business appearing as a row in blog.comment's permissions matrix).

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'role_resource_fkey'
  ) THEN
    ALTER TABLE "half_orm_meta.api".role
      ADD CONSTRAINT role_resource_fkey FOREIGN KEY (schemaname, relname)
      REFERENCES "half_orm_meta.api".resource(schemaname, relname);
  END IF;
END $$;

CREATE OR REPLACE FUNCTION "half_orm_meta.api".check_role_deletable()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.name IN ('anonymous', 'connected', 'admin') THEN
    RAISE EXCEPTION 'Role "%" is a system role and cannot be deleted', OLD.name;
  END IF;
  IF NOT OLD.deletable THEN
    RAISE EXCEPTION 'Role "%" cannot be deleted (deletable = FALSE)', OLD.name;
  END IF;
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'trg_check_role_deletable'
      AND tgrelid = '"half_orm_meta.api".role'::regclass
  ) THEN
    CREATE TRIGGER trg_check_role_deletable
      BEFORE DELETE ON "half_orm_meta.api".role
      FOR EACH ROW EXECUTE FUNCTION "half_orm_meta.api".check_role_deletable();
  END IF;
END $$;

CREATE OR REPLACE FUNCTION "half_orm_meta.api".check_role_cycle()
RETURNS TRIGGER AS $$
DECLARE
  v_current text;
BEGIN
  v_current := NEW.parent_name;
  WHILE v_current IS NOT NULL LOOP
    IF v_current = NEW.name THEN
      RAISE EXCEPTION 'Role "%" would create a cycle in the role hierarchy', NEW.name;
    END IF;
    SELECT parent_name INTO v_current
      FROM "half_orm_meta.api".role WHERE name = v_current;
  END LOOP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'trg_check_role_cycle'
      AND tgrelid = '"half_orm_meta.api".role'::regclass
  ) THEN
    CREATE TRIGGER trg_check_role_cycle
      BEFORE INSERT OR UPDATE ON "half_orm_meta.api".role
      FOR EACH ROW EXECUTE FUNCTION "half_orm_meta.api".check_role_cycle();
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".route (
  schema_name  text NOT NULL,
  table_name   text NOT NULL,
  verb         text NOT NULL CHECK (verb IN ('GET', 'POST', 'PUT', 'DELETE')),
  deprecated   boolean NOT NULL DEFAULT FALSE,
  PRIMARY KEY (schema_name, table_name, verb)
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'route_resource_fkey'
  ) THEN
    ALTER TABLE "half_orm_meta.api".route
      ADD CONSTRAINT route_resource_fkey FOREIGN KEY (schema_name, table_name)
      REFERENCES "half_orm_meta.api".resource(schemaname, relname);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".field (
  schema_name  text NOT NULL,
  table_name   text NOT NULL,
  column_name  text NOT NULL,
  deprecated   boolean NOT NULL DEFAULT FALSE,
  label_order  integer,
  PRIMARY KEY (schema_name, table_name, column_name)
);

ALTER TABLE "half_orm_meta.api".field
  ADD COLUMN IF NOT EXISTS label_order integer;
-- NULL = not a label field. 0, 1, 2... = concatenation order for the
-- resource's display label (used by the FK select combobox and the
-- global search result formatter).

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'field_resource_fkey'
  ) THEN
    ALTER TABLE "half_orm_meta.api".field
      ADD CONSTRAINT field_resource_fkey FOREIGN KEY (schema_name, table_name)
      REFERENCES "half_orm_meta.api".resource(schemaname, relname);
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".access (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_name       text NOT NULL REFERENCES "half_orm_meta.api".role(name) ON DELETE CASCADE,
  schema_name     text NOT NULL,
  table_name      text NOT NULL,
  verb            text NOT NULL,
  FOREIGN KEY (schema_name, table_name, verb)
    REFERENCES "half_orm_meta.api".route(schema_name, table_name, verb) ON DELETE CASCADE,
  UNIQUE (role_name, schema_name, table_name, verb)
);

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".field_access_in (
  access_id  uuid NOT NULL REFERENCES "half_orm_meta.api".access(id) ON DELETE CASCADE,
  field_name text NOT NULL,
  PRIMARY KEY (access_id, field_name)
);

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".field_access_out (
  access_id  uuid NOT NULL REFERENCES "half_orm_meta.api".access(id) ON DELETE CASCADE,
  field_name text NOT NULL,
  PRIMARY KEY (access_id, field_name)
);

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".filter (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  schema_name text NOT NULL,
  table_name  text NOT NULL,
  name        text NOT NULL,
  UNIQUE (schema_name, table_name, name)
);

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".access_filter (
  access_id uuid NOT NULL REFERENCES "half_orm_meta.api".access(id) ON DELETE CASCADE,
  filter_id uuid NOT NULL REFERENCES "half_orm_meta.api".filter(id) ON DELETE CASCADE,
  PRIMARY KEY (access_id, filter_id)
);

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".field_access_fk_auto (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  access_id    uuid NOT NULL REFERENCES "half_orm_meta.api".access(id) ON DELETE CASCADE,
  field_name   text NOT NULL,
  resolve_rule text NOT NULL CHECK (resolve_rule IN ('connected_user', 'context', 'select')),
  UNIQUE (access_id, field_name)
);

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".field_access_searchable (
  access_id  uuid NOT NULL,
  field_name text NOT NULL,
  role_name  text REFERENCES "half_orm_meta.api".role(name) ON DELETE CASCADE,
  PRIMARY KEY (access_id, field_name),
  FOREIGN KEY (access_id, field_name)
    REFERENCES "half_orm_meta.api".field_access_out(access_id, field_name)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".user_role (
  user_id   uuid NOT NULL,
  role_name text NOT NULL REFERENCES "half_orm_meta.api".role(name) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_name)
);

CREATE OR REPLACE FUNCTION "half_orm_meta.api".check_filter_relation()
RETURNS TRIGGER AS $$
DECLARE
  v_fs text; v_ft text; v_as text; v_at text;
BEGIN
  SELECT schema_name, table_name INTO v_fs, v_ft
    FROM "half_orm_meta.api".filter WHERE id = NEW.filter_id;
  SELECT schema_name, table_name INTO v_as, v_at
    FROM "half_orm_meta.api".access WHERE id = NEW.access_id;
  IF v_fs != v_as OR v_ft != v_at THEN
    RAISE EXCEPTION 'Filter (%.%) cannot be applied to access on %.%',
      v_fs, v_ft, v_as, v_at;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'trg_check_filter_relation'
      AND tgrelid = '"half_orm_meta.api".access_filter'::regclass
  ) THEN
    CREATE TRIGGER trg_check_filter_relation
      BEFORE INSERT OR UPDATE ON "half_orm_meta.api".access_filter
      FOR EACH ROW EXECUTE FUNCTION "half_orm_meta.api".check_filter_relation();
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- field.id migration — surrogate PK, replacing (schema_name, table_name,
-- column_name) as the primary key (kept as a UNIQUE constraint for
-- name-based lookup). Lets field_access_in/out/searchable/fk_auto
-- reference a single field_id column with a real FK (ON DELETE CASCADE)
-- instead of their own free-text field_name — nothing enforced that
-- field_name actually named a column known to `field`, so a stale/
-- typo'd/dropped-column reference could linger with no error and no
-- cleanup on column removal. Placed here (after every original CREATE
-- TABLE, including field_access_searchable's own field_name-based FK to
-- field_access_out) so no still-needed field_name column is dropped
-- before a later CREATE TABLE IF NOT EXISTS statement needs to reference it.
-- ---------------------------------------------------------------------------

ALTER TABLE "half_orm_meta.api".field
  ADD COLUMN IF NOT EXISTS id uuid DEFAULT gen_random_uuid();
UPDATE "half_orm_meta.api".field SET id = gen_random_uuid() WHERE id IS NULL;
ALTER TABLE "half_orm_meta.api".field ALTER COLUMN id SET NOT NULL;

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'field_pkey' AND contype = 'p'
  ) THEN
    ALTER TABLE "half_orm_meta.api".field DROP CONSTRAINT field_pkey;
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_id_pkey') THEN
    ALTER TABLE "half_orm_meta.api".field ADD CONSTRAINT field_id_pkey PRIMARY KEY (id);
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_natural_key') THEN
    ALTER TABLE "half_orm_meta.api".field
      ADD CONSTRAINT field_natural_key UNIQUE (schema_name, table_name, column_name);
  END IF;
END $$;

-- field_access_in / field_access_out / field_access_fk_auto /
-- field_access_searchable: backfill field_id from the still-present
-- field_name (each resolved independently via access + field — not by
-- reading field_access_out's own field_id, so this doesn't depend on that
-- table's migration having already run), then swap constraints, then drop
-- field_name. Constraint drops/adds are ordered by dependency:
-- field_access_searchable's OLD fkey (into field_access_out's OLD pkey)
-- must go before field_access_out's OLD pkey is dropped, and
-- field_access_searchable's NEW fkey (into field_access_out's NEW pkey)
-- can only be added after that new pkey exists.

ALTER TABLE "half_orm_meta.api".field_access_in         ADD COLUMN IF NOT EXISTS field_id uuid;
ALTER TABLE "half_orm_meta.api".field_access_out        ADD COLUMN IF NOT EXISTS field_id uuid;
ALTER TABLE "half_orm_meta.api".field_access_fk_auto    ADD COLUMN IF NOT EXISTS field_id uuid;
ALTER TABLE "half_orm_meta.api".field_access_searchable ADD COLUMN IF NOT EXISTS field_id uuid;

-- Guarded (not a bare UPDATE): field_name is dropped at the end of this
-- migration, so on every run after the first it no longer exists — a bare
-- UPDATE referencing it would fail to plan at all (unlike a WHERE clause
-- that just matches zero rows). Each guard checks that field_name is
-- still there before the statement referencing it is ever prepared.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'half_orm_meta.api' AND table_name = 'field_access_in' AND column_name = 'field_name') THEN
    UPDATE "half_orm_meta.api".field_access_in t
      SET field_id = f.id
      FROM "half_orm_meta.api".access a, "half_orm_meta.api".field f
      WHERE a.id = t.access_id
        AND f.schema_name = a.schema_name AND f.table_name = a.table_name
        AND f.column_name = t.field_name
        AND t.field_id IS NULL;
  END IF;
END $$;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'half_orm_meta.api' AND table_name = 'field_access_out' AND column_name = 'field_name') THEN
    UPDATE "half_orm_meta.api".field_access_out t
      SET field_id = f.id
      FROM "half_orm_meta.api".access a, "half_orm_meta.api".field f
      WHERE a.id = t.access_id
        AND f.schema_name = a.schema_name AND f.table_name = a.table_name
        AND f.column_name = t.field_name
        AND t.field_id IS NULL;
  END IF;
END $$;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'half_orm_meta.api' AND table_name = 'field_access_fk_auto' AND column_name = 'field_name') THEN
    UPDATE "half_orm_meta.api".field_access_fk_auto t
      SET field_id = f.id
      FROM "half_orm_meta.api".access a, "half_orm_meta.api".field f
      WHERE a.id = t.access_id
        AND f.schema_name = a.schema_name AND f.table_name = a.table_name
        AND f.column_name = t.field_name
        AND t.field_id IS NULL;
  END IF;
END $$;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'half_orm_meta.api' AND table_name = 'field_access_searchable' AND column_name = 'field_name') THEN
    UPDATE "half_orm_meta.api".field_access_searchable t
      SET field_id = f.id
      FROM "half_orm_meta.api".access a, "half_orm_meta.api".field f
      WHERE a.id = t.access_id
        AND f.schema_name = a.schema_name AND f.table_name = a.table_name
        AND f.column_name = t.field_name
        AND t.field_id IS NULL;
  END IF;
END $$;

DELETE FROM "half_orm_meta.api".field_access_in         WHERE field_id IS NULL;
DELETE FROM "half_orm_meta.api".field_access_out        WHERE field_id IS NULL;
DELETE FROM "half_orm_meta.api".field_access_fk_auto    WHERE field_id IS NULL;
DELETE FROM "half_orm_meta.api".field_access_searchable WHERE field_id IS NULL;
-- A stale/mismatched field_name that no longer matches any live column —
-- exactly the dangling-reference case this migration closes — is dropped
-- rather than left to violate the NOT NULL/FK added next.

ALTER TABLE "half_orm_meta.api".field_access_in         ALTER COLUMN field_id SET NOT NULL;
ALTER TABLE "half_orm_meta.api".field_access_out        ALTER COLUMN field_id SET NOT NULL;
ALTER TABLE "half_orm_meta.api".field_access_fk_auto    ALTER COLUMN field_id SET NOT NULL;
ALTER TABLE "half_orm_meta.api".field_access_searchable ALTER COLUMN field_id SET NOT NULL;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_in_field_id_fkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_in
      ADD CONSTRAINT field_access_in_field_id_fkey FOREIGN KEY (field_id)
      REFERENCES "half_orm_meta.api".field(id) ON DELETE CASCADE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_out_field_id_fkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_out
      ADD CONSTRAINT field_access_out_field_id_fkey FOREIGN KEY (field_id)
      REFERENCES "half_orm_meta.api".field(id) ON DELETE CASCADE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_fk_auto_field_id_fkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_fk_auto
      ADD CONSTRAINT field_access_fk_auto_field_id_fkey FOREIGN KEY (field_id)
      REFERENCES "half_orm_meta.api".field(id) ON DELETE CASCADE;
  END IF;
END $$;

-- Drop field_access_searchable's OLD fkey FIRST — it depends on
-- field_access_out_pkey, which the next block drops.
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint
             WHERE conname = 'field_access_searchable_access_id_field_name_fkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_searchable
      DROP CONSTRAINT field_access_searchable_access_id_field_name_fkey;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint
             WHERE conname = 'field_access_searchable_pkey' AND contype = 'p') THEN
    ALTER TABLE "half_orm_meta.api".field_access_searchable DROP CONSTRAINT field_access_searchable_pkey;
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_in_pkey' AND contype = 'p') THEN
    ALTER TABLE "half_orm_meta.api".field_access_in DROP CONSTRAINT field_access_in_pkey;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_out_pkey' AND contype = 'p') THEN
    ALTER TABLE "half_orm_meta.api".field_access_out DROP CONSTRAINT field_access_out_pkey;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_fk_auto_access_id_field_name_key') THEN
    ALTER TABLE "half_orm_meta.api".field_access_fk_auto
      DROP CONSTRAINT field_access_fk_auto_access_id_field_name_key;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_in_id_pkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_in ADD CONSTRAINT field_access_in_id_pkey PRIMARY KEY (access_id, field_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_out_id_pkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_out ADD CONSTRAINT field_access_out_id_pkey PRIMARY KEY (access_id, field_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_fk_auto_access_id_field_id_key') THEN
    ALTER TABLE "half_orm_meta.api".field_access_fk_auto
      ADD CONSTRAINT field_access_fk_auto_access_id_field_id_key UNIQUE (access_id, field_id);
  END IF;
END $$;

-- Now that field_access_out's new (access_id, field_id) pkey exists,
-- field_access_searchable can get its own new pkey + fkey into it.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_searchable_id_pkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_searchable
      ADD CONSTRAINT field_access_searchable_id_pkey PRIMARY KEY (access_id, field_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'field_access_searchable_out_fkey') THEN
    ALTER TABLE "half_orm_meta.api".field_access_searchable
      ADD CONSTRAINT field_access_searchable_out_fkey FOREIGN KEY (access_id, field_id)
      REFERENCES "half_orm_meta.api".field_access_out(access_id, field_id) ON DELETE CASCADE;
  END IF;
END $$;

-- All four tables' field_id columns are in place — safe to drop field_name now.
ALTER TABLE "half_orm_meta.api".field_access_in         DROP COLUMN IF EXISTS field_name;
ALTER TABLE "half_orm_meta.api".field_access_out        DROP COLUMN IF EXISTS field_name;
ALTER TABLE "half_orm_meta.api".field_access_fk_auto    DROP COLUMN IF EXISTS field_name;
ALTER TABLE "half_orm_meta.api".field_access_searchable DROP COLUMN IF EXISTS field_name;

CREATE OR REPLACE FUNCTION "half_orm_meta.api".check_field_not_inherited()
RETURNS TRIGGER AS $$
DECLARE
  v_role   text;
  v_schema text;
  v_table  text;
  v_verb   text;
  v_parent text;
  v_anc_id uuid;
BEGIN
  SELECT a.role_name, a.schema_name, a.table_name, a.verb
    INTO v_role, v_schema, v_table, v_verb
    FROM "half_orm_meta.api".access a WHERE a.id = NEW.access_id;

  SELECT r.parent_name INTO v_parent
    FROM "half_orm_meta.api".role r WHERE r.name = v_role;

  WHILE v_parent IS NOT NULL LOOP
    SELECT a.id INTO v_anc_id
      FROM "half_orm_meta.api".access a
     WHERE a.role_name   = v_parent
       AND a.schema_name = v_schema
       AND a.table_name  = v_table
       AND a.verb        = v_verb;

    IF FOUND THEN
      IF TG_TABLE_NAME = 'field_access_in' THEN
        IF EXISTS (SELECT 1 FROM "half_orm_meta.api".field_access_in
                    WHERE access_id = v_anc_id AND field_id = NEW.field_id) THEN
          RAISE EXCEPTION
            'Field "%" is already granted to ancestor role "%" — store only additional fields',
            NEW.field_id, v_parent;
        END IF;
      ELSE
        IF EXISTS (SELECT 1 FROM "half_orm_meta.api".field_access_out
                    WHERE access_id = v_anc_id AND field_id = NEW.field_id) THEN
          RAISE EXCEPTION
            'Field "%" is already granted to ancestor role "%" — store only additional fields',
            NEW.field_id, v_parent;
        END IF;
      END IF;
    END IF;

    SELECT r.parent_name INTO v_parent
      FROM "half_orm_meta.api".role r WHERE r.name = v_parent;
  END LOOP;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'trg_check_field_in_not_inherited'
      AND tgrelid = '"half_orm_meta.api".field_access_in'::regclass
  ) THEN
    CREATE TRIGGER trg_check_field_in_not_inherited
      BEFORE INSERT ON "half_orm_meta.api".field_access_in
      FOR EACH ROW EXECUTE FUNCTION "half_orm_meta.api".check_field_not_inherited();
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'trg_check_field_out_not_inherited'
      AND tgrelid = '"half_orm_meta.api".field_access_out'::regclass
  ) THEN
    CREATE TRIGGER trg_check_field_out_not_inherited
      BEFORE INSERT ON "half_orm_meta.api".field_access_out
      FOR EACH ROW EXECUTE FUNCTION "half_orm_meta.api".check_field_not_inherited();
  END IF;
END $$;
"""

# DDL for the "half_orm_meta.identity" schema — federated identity between
# independently-deployed half-orm-gen projects ("peers"). Always created
# alongside "half_orm_meta.api" (cheap, harmless if unused) but inert until
# an admin actually registers peers via /ho_admin/peer. See
# planning/identite_federee.md for the full design rationale.
HO_IDENTITY_DDL = """\
CREATE SCHEMA IF NOT EXISTS "half_orm_meta.identity";

CREATE TABLE IF NOT EXISTS "half_orm_meta.identity".peer (
  id             uuid PRIMARY KEY,
  name           text NOT NULL,
  url            text NOT NULL,
  frontend_url   text,
  jwt_public_key text,
  trusted        boolean NOT NULL DEFAULT TRUE,
  created_at     timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- id: NOT locally generated (no DEFAULT) — it's the peer's OWN self-declared
-- HO_PEER_ID, received via its registration card (planning/identite_federee.md
-- section 4bis), so it can be used as the lookup key in delegation URLs
-- without depending on the free-text `name` this admin happened to type.
-- frontend_url: this peer's frontend base URL (no API version prefix),
-- used for cross-site navigation — distinct from `url`, the API base.

CREATE TABLE IF NOT EXISTS "half_orm_meta.identity"."user" (
  id             uuid PRIMARY KEY,
  origin_peer_id uuid REFERENCES "half_orm_meta.identity".peer(id) ON DELETE SET NULL,
  name           text,
  email          text,
  password_hash  text,
  first_seen_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at   timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- id: NOT generated locally — the "sub" claim of the person's JWT, immuable.
-- origin_peer_id: which peer first vouched for this identity (NULL = born
-- locally on this peer). password_hash: only set for accounts authenticated
-- locally on THIS peer (HO_LOCAL_AUTH=db) — never set for an identity whose
-- origin is another peer, which authenticates via that peer's token instead.

CREATE TABLE IF NOT EXISTS "half_orm_meta.identity".login_state (
  state      text PRIMARY KEY,
  peer_id    uuid NOT NULL REFERENCES "half_orm_meta.identity".peer(id) ON DELETE CASCADE,
  return_to  text,
  created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Server-side anti-CSRF state for the login-delegation redirect/callback
-- flow (planning/identite_federee.md section 4) — single-use, short-lived
-- (checked against created_at at validation time), deleted once consumed.
"""
