-- pages_demo fixtures: identity pre-seed (federation) + a few wiki pages.
--
-- Loaded by `make demo-federate`, AFTER blog_demo has been registered as a
-- trusted peer in pages_demo's own "half_orm_meta.identity".peer table (see
-- Makefile's demo-federate target — it inserts that row first, dynamically,
-- with blog_demo's real public key, then this file runs).
--
-- Pre-seeds pages_demo's own "half_orm_meta.identity"."user" with blog_demo's
-- REAL user UUIDs (fixtures/blog_demo_data.sql), as if they had already
-- federated in via the SSO redirect/callback flow — lets wiki.page.author_id
-- have a real, enforced FK to "half_orm_meta.identity"."user" without
-- requiring an actual browser round-trip to populate it for the demo.

BEGIN;

-- ── pre-seeded identities (origin: blog_demo) ───────────────────────────────

INSERT INTO "half_orm_meta.identity"."user" (id, origin_peer_id, name, email)
SELECT v.id, p.id, v.name, v.email
FROM (VALUES
    ('a0000000-0000-0000-0000-000000000000'::uuid, 'Admin',        'admin@half-orm.org'),
    ('a1000000-0000-0000-0000-000000000001'::uuid, 'Alice Martin', 'alice@half-orm.org'),
    ('a1000000-0000-0000-0000-000000000002'::uuid, 'Bob Dupont',   'bob@half-orm.org'),
    ('a1000000-0000-0000-0000-000000000003'::uuid, 'Clara Nguyen', 'clara@half-orm.org')
) AS v(id, name, email)
CROSS JOIN (SELECT id FROM "half_orm_meta.identity".peer WHERE name = 'blog_demo') AS p
ON CONFLICT (id) DO NOTHING;

-- blog_demo's Admin is also admin here — authorization stays local per peer
-- (planning/identite_federee.md): identity is federated, the admin *grant*
-- is not, it has to be made explicitly in each peer.
INSERT INTO "half_orm_meta.api".user_role (user_id, role_name) VALUES
    ('a0000000-0000-0000-0000-000000000000', 'admin')
ON CONFLICT DO NOTHING;

-- ── wiki pages (authored by the pre-seeded, federated-in identities) ────────

INSERT INTO wiki.page (id, title, content, author_id) VALUES
    ('c3000000-0000-0000-0000-000000000001',
     'Bienvenue sur ce wiki',
     E'# Bienvenue\n\nCe wiki est un exemple de second projet half-orm-gen '
     'partageant ses utilisateurs avec `blog_demo` via la fédération '
     'd''identité — voir `planning/identite_federee.md`.',
     'a1000000-0000-0000-0000-000000000001'),

    ('c3000000-0000-0000-0000-000000000002',
     'Comment fonctionne la fédération ?',
     E'# Fédération d''identité\n\nChaque *peer* peut émettre ses propres '
     'jetons signés (RS256) et faire confiance explicitement à d''autres '
     'peers, sans autorité centrale. Voir `half_orm_meta.identity.peer`.',
     'a1000000-0000-0000-0000-000000000002'),

    ('c3000000-0000-0000-0000-000000000003',
     'Contraintes d''intégrité et identités partagées',
     E'# Intégrité\n\n`wiki.page.author_id` référence réellement '
     '`half_orm_meta.identity."user"(id)` par une vraie contrainte de '
     'clé étrangère, pas juste un UUID logiquement lié.',
     'a1000000-0000-0000-0000-000000000003')
ON CONFLICT DO NOTHING;

COMMIT;
