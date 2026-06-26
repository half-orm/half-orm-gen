-- blog_demo access rules — translation of the former CRUD_ACCESS Python dicts.
-- Run after `half_orm gen api` (which seeds routes and fields via reconcile_catalog).

BEGIN;

-- ── blog.author ───────────────────────────────────────────────────────────────

INSERT INTO "half_orm_meta.api".access
    (role_name, schema_name, table_name, verb, all_fields_in, all_fields_out)
VALUES
    ('anonymous', 'blog', 'author', 'GET',    FALSE, FALSE),
    ('connected', 'blog', 'author', 'GET',    FALSE, TRUE),
    ('connected', 'blog', 'author', 'POST',   FALSE, TRUE),
    ('connected', 'blog', 'author', 'PUT',    FALSE, TRUE),
    ('admin',     'blog', 'author', 'DELETE', TRUE,  TRUE)
ON CONFLICT (role_name, schema_name, table_name, verb) DO NOTHING;

-- anonymous/GET: out = [id, name]
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('id'), ('name')) AS f(field_name)
WHERE a.role_name = 'anonymous'
  AND a.schema_name = 'blog' AND a.table_name = 'author' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- connected/POST: in = [name, email]
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('name'), ('email')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'author' AND a.verb = 'POST'
ON CONFLICT DO NOTHING;

-- connected/PUT: in = [name, email]
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
    (role_name, schema_name, table_name, verb, all_fields_in, all_fields_out)
VALUES
    ('anonymous', 'blog', 'post', 'GET',    FALSE, FALSE),
    ('connected', 'blog', 'post', 'GET',    FALSE, TRUE),
    ('connected', 'blog', 'post', 'POST',   FALSE, TRUE),
    ('connected', 'blog', 'post', 'PUT',    FALSE, TRUE),
    ('admin',     'blog', 'post', 'DELETE', TRUE,  TRUE)
ON CONFLICT (role_name, schema_name, table_name, verb) DO NOTHING;

-- anonymous/GET: out = [id, title, published, author_id]
INSERT INTO "half_orm_meta.api".field_access_out (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('id'), ('title'), ('published'), ('author_id')) AS f(field_name)
WHERE a.role_name = 'anonymous'
  AND a.schema_name = 'blog' AND a.table_name = 'post' AND a.verb = 'GET'
ON CONFLICT DO NOTHING;

-- connected/POST: in = [title, content, author_id]
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('title'), ('content'), ('author_id')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'post' AND a.verb = 'POST'
ON CONFLICT DO NOTHING;

-- connected/PUT: in = [title, content, published]
INSERT INTO "half_orm_meta.api".field_access_in (access_id, field_name)
SELECT a.id, f.field_name
FROM "half_orm_meta.api".access a
CROSS JOIN (VALUES ('title'), ('content'), ('published')) AS f(field_name)
WHERE a.role_name = 'connected'
  AND a.schema_name = 'blog' AND a.table_name = 'post' AND a.verb = 'PUT'
ON CONFLICT DO NOTHING;


-- ── blog.comment ──────────────────────────────────────────────────────────────

INSERT INTO "half_orm_meta.api".access
    (role_name, schema_name, table_name, verb, all_fields_in, all_fields_out)
VALUES
    ('anonymous', 'blog', 'comment', 'GET',    FALSE, FALSE),
    ('connected', 'blog', 'comment', 'POST',   FALSE, TRUE),
    ('admin',     'blog', 'comment', 'DELETE', TRUE,  TRUE)
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
    (role_name, schema_name, table_name, verb, all_fields_in, all_fields_out)
VALUES
    ('anonymous', 'blog', 'comment_type', 'GET', FALSE, TRUE)
ON CONFLICT (role_name, schema_name, table_name, verb) DO NOTHING;

COMMIT;
