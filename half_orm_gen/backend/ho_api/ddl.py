"""DDL for the "half_orm_meta.api" schema."""

HO_API_DDL = """\
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE SCHEMA IF NOT EXISTS "half_orm_meta.api";

CREATE TABLE IF NOT EXISTS "half_orm_meta.api".role (
  name        text PRIMARY KEY,
  deletable   boolean NOT NULL DEFAULT TRUE,
  parent_name text REFERENCES "half_orm_meta.api".role(name)
);

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
                    WHERE access_id = v_anc_id AND field_name = NEW.field_name) THEN
          RAISE EXCEPTION
            'Field "%" is already granted to ancestor role "%" — store only additional fields',
            NEW.field_name, v_parent;
        END IF;
      ELSE
        IF EXISTS (SELECT 1 FROM "half_orm_meta.api".field_access_out
                    WHERE access_id = v_anc_id AND field_name = NEW.field_name) THEN
          RAISE EXCEPTION
            'Field "%" is already granted to ancestor role "%" — store only additional fields',
            NEW.field_name, v_parent;
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
"""
