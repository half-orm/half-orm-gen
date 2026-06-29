-- blog_demo access rules.
-- Run after `half_orm gen api` (which seeds routes and fields via reconcile_catalog).

BEGIN;

-- ── blog.author ───────────────────────────────────────────────────────────────

INSERT INTO "half_orm_meta.api".access
    (role_name, schema_name, table_name, verb)
VALUES
    ('anonymous', 'blog', 'author', 'GET'),
    ('connected', 'blog', 'author', 'GET'),
    ('connected', 'blog', 'author', 'POST'),
    ('connected', 'blog', 'author', 'PUT'),
    ('admin',     'blog', 'author', 'DELETE')
ON CONFLICT (role_name, schema_name, table_name, verb) DO NOTHING;

-- anonymous/GET: out = [id, name]
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('id'), ('name')) AS f(field_name)
WHERE a.role_name = 'anonymous'
  AND a.schema_name = 'blog' AND a.table_name = 'author' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- connected/GET: out = [id, name, email]
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('id'), ('name'), ('email')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'author' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- connected/POST: in = [name, email]  (out falls back to connected/GET out)
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('name'), ('email')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'author' AND a.verb = 'POST'
ON CONFLICT DO NOTHING;

-- connected/PUT: in = [name, email]  (out falls back to connected/GET out)
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('name'), ('email')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'author' AND a.verb = 'PUT'
ON CONFLICT DO NOTHING;


-- ── blog.post ─────────────────────────────────────────────────────────────────
-- Note: the former "filter": {"published": True} for anonymous/GET is not stored
-- here — it will be re-implemented as a @ho_api_role method in blog/post.py.

INSERT INTO "half_orm_meta.api".access
    (role_name, schema_name, table_name, verb)
VALUES
    ('anonymous', 'blog', 'post', 'GET'),
    ('connected', 'blog', 'post', 'GET'),
    ('connected', 'blog', 'post', 'POST'),
    ('connected', 'blog', 'post', 'PUT'),
    ('admin',     'blog', 'post', 'DELETE')
ON CONFLICT (role_name, schema_name, table_name, verb) DO NOTHING;

-- anonymous/GET: out = [id, title, published, author_id]
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('id'), ('title'), ('published'), ('author_id')) AS f(field_name)
WHERE a.role_name = 'anonymous'
  AND a.schema_name = 'blog' AND a.table_name = 'post' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- connected/GET: out = [id, title, content, published, author_id]
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('id'), ('title'), ('content'), ('published'), ('author_id')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'post' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- connected/POST: in = [title, content, author_id]  (out falls back to connected/GET out)
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('title'), ('content'), ('author_id')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'post' AND a.verb = 'POST'
ON CONFLICT DO NOTHING;

-- connected/PUT: in = [title, content, published]  (out falls back to connected/GET out)
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('title'), ('content'), ('published')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'post' AND a.verb = 'PUT'
ON CONFLICT DO NOTHING;


-- ── blog.comment ──────────────────────────────────────────────────────────────

INSERT INTO "half_orm_meta.api".access
    (role_name, schema_name, table_name, verb)
VALUES
    ('anonymous', 'blog', 'comment', 'GET'),
    ('connected', 'blog', 'comment', 'POST'),
    ('admin',     'blog', 'comment', 'DELETE')
ON CONFLICT (role_name, schema_name, table_name, verb) DO NOTHING;

-- anonymous/GET: out = [id, content, post_id, author_id, comment_type]
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('id'), ('content'), ('post_id'), ('author_id'), ('comment_type')) AS f(field_name)
WHERE a.role_name = 'anonymous'
  AND a.schema_name = 'blog' AND a.table_name = 'comment' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- connected/POST: in = [content, post_id, author_id, comment_type]
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('content'), ('post_id'), ('author_id'), ('comment_type')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'comment' AND a.verb = 'POST'
ON CONFLICT DO NOTHING;


-- ── blog.comment_type ─────────────────────────────────────────────────────────

INSERT INTO "half_orm_meta.api".access
    (role_name, schema_name, table_name, verb)
VALUES
    ('anonymous', 'blog', 'comment_type', 'GET')
ON CONFLICT (role_name, schema_name, table_name, verb) DO NOTHING;

-- anonymous/GET: out = [name]  (only column of comment_type)
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, 'name'
FROM "half_orm_meta.api".access a
WHERE a.role_name = 'anonymous'
  AND a.schema_name = 'blog' AND a.table_name = 'comment_type' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- ── user_role FK → actor.user ─────────────────────────────────────────────────
-- actor.user already exists (created by the schema patch before gen api).
-- user_role was created by half_orm gen api (ddl.py).

ALTER TABLE "half_orm_meta.api".user_role
  DROP CONSTRAINT IF EXISTS user_role_user_id_fk;
ALTER TABLE "half_orm_meta.api".user_role
  ADD CONSTRAINT user_role_user_id_fk
  FOREIGN KEY (user_id) REFERENCES actor."user"(id) ON DELETE CASCADE;

COMMIT;
