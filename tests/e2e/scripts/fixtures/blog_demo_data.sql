-- blog_demo fixtures: 5 authors, 10 posts, 20 comments (7 reviews)

BEGIN;

-- ── comment types ────────────────────────────────────────────────────────────

INSERT INTO blog.comment_type (name) VALUES
    ('comment'),
    ('review'),
    ('question')
ON CONFLICT DO NOTHING;

-- ── authors ──────────────────────────────────────────────────────────────────
-- Registered in "half_orm_meta.identity"."user" (the shared federated
-- identity table, planning/identite_federee.md), NOT a separate local
-- actor.user table — blog_demo uses identity."user" as its only user store.
-- password_hash is bcrypt("halform-demo") for every fixture account, so any
-- of them can log in locally with that password.

INSERT INTO "half_orm_meta.identity"."user" (id, name, email, password_hash) VALUES
    ('a0000000-0000-0000-0000-000000000000', 'Admin',          'admin@half-orm.org', '$2b$12$KgqfQqm9ucmuTgZUt4ooA.wK.WU3/ujDvUJp14vrQSDIOnt6xbPAe'),
    ('a1000000-0000-0000-0000-000000000001', 'Alice Martin',   'alice@half-orm.org', '$2b$12$KgqfQqm9ucmuTgZUt4ooA.wK.WU3/ujDvUJp14vrQSDIOnt6xbPAe'),
    ('a1000000-0000-0000-0000-000000000002', 'Bob Dupont',     'bob@half-orm.org',   '$2b$12$KgqfQqm9ucmuTgZUt4ooA.wK.WU3/ujDvUJp14vrQSDIOnt6xbPAe'),
    ('a1000000-0000-0000-0000-000000000003', 'Clara Nguyen',   'clara@half-orm.org', '$2b$12$KgqfQqm9ucmuTgZUt4ooA.wK.WU3/ujDvUJp14vrQSDIOnt6xbPAe'),
    ('a1000000-0000-0000-0000-000000000004', 'David Leclerc',  'david@half-orm.org', '$2b$12$KgqfQqm9ucmuTgZUt4ooA.wK.WU3/ujDvUJp14vrQSDIOnt6xbPAe'),
    ('a1000000-0000-0000-0000-000000000005', 'Eva Rossi',      'eva@half-orm.org',   '$2b$12$KgqfQqm9ucmuTgZUt4ooA.wK.WU3/ujDvUJp14vrQSDIOnt6xbPAe');

-- ── posts ────────────────────────────────────────────────────────────────────

INSERT INTO blog.post (id, title, content, published, author_id) VALUES
    ('b2000000-0000-0000-0000-000000000001',
     'Introduction à halfORM',
     'halfORM est un ORM Python minimaliste basé sur PostgreSQL. Il repose sur une approche sans migration : le modèle relationnel est la source de vérité.',
     TRUE,  'a1000000-0000-0000-0000-000000000001'),

    ('b2000000-0000-0000-0000-000000000002',
     'Litestar vs FastAPI : premier bilan',
     'Deux frameworks asynchrones modernes, deux philosophies. Litestar mise sur la typage fort ; FastAPI sur la simplicité de prise en main.',
     TRUE,  'a1000000-0000-0000-0000-000000000002'),

    ('b2000000-0000-0000-0000-000000000003',
     'Svelte 5 et les runes : ce qui change',
     'Svelte 5 introduit les runes ($state, $derived, $effect) pour remplacer le système de réactivité implicite. Un changement profond mais cohérent.',
     TRUE,  'a1000000-0000-0000-0000-000000000003'),

    ('b2000000-0000-0000-0000-000000000004',
     'PostgreSQL full-text search en pratique',
     'tsvector, tsquery et les index GIN : comment indexer du texte francophone avec la bonne configuration de langue.',
     TRUE,  'a1000000-0000-0000-0000-000000000004'),

    ('b2000000-0000-0000-0000-000000000005',
     'UUID v4 ou v7 pour vos PKs ?',
     'UUID v4 est aléatoire et provoque de la fragmentation d''index. UUID v7 est ordonné dans le temps : bien meilleur pour les PKs en B-Tree.',
     TRUE,  'a1000000-0000-0000-0000-000000000005'),

    ('b2000000-0000-0000-0000-000000000006',
     'Asyncio en production : pièges courants',
     'gather(), TaskGroup, annulation propre et gestion des exceptions : un tour d''horizon des erreurs classiques en code async Python.',
     TRUE,  'a1000000-0000-0000-0000-000000000001'),

    ('b2000000-0000-0000-0000-000000000007',
     'Générer une API REST depuis un schéma SQL',
     'CRUD_ACCESS et halfORM-litestar permettent de déclarer les droits d''accès directement dans le modèle Python, sans écrire de routes à la main.',
     TRUE,  'a1000000-0000-0000-0000-000000000002'),

    ('b2000000-0000-0000-0000-000000000008',
     'Tailwind CSS 4 : ce qui arrive',
     'La configuration passe en CSS natif, les utilitaires sont générés à la demande. Le fichier tailwind.config.js disparaît presque entièrement.',
     FALSE, 'a1000000-0000-0000-0000-000000000003'),

    ('b2000000-0000-0000-0000-000000000009',
     'Pydantic v2 : migration pratique',
     'model_dump() remplace dict(), model_validate() remplace parse_obj(). Le gain de performance est réel mais la migration demande de l''attention.',
     TRUE,  'a1000000-0000-0000-0000-000000000004'),

    ('b2000000-0000-0000-0000-000000000010',
     'TypeScript strict : à quoi ça sert vraiment',
     'strictNullChecks, noUncheckedIndexedAccess, exactOptionalPropertyTypes : chaque option strict et pourquoi elle vaut le coût.',
     FALSE, 'a1000000-0000-0000-0000-000000000005');

-- ── comments (20 total : 7 reviews, 11 comments, 2 questions) ────────────────

INSERT INTO blog.comment (id, content, post_id, author_id, comment_type) VALUES

    -- post 1 (Introduction à halfORM) — 3 commentaires
    ('c3000000-0000-0000-0000-000000000001',
     'Très bon article, j''utilise halfORM depuis 6 mois et la courbe d''apprentissage est douce.',
     'b2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002', 'comment'),

    ('c3000000-0000-0000-0000-000000000002',
     '★★★★★ — Exactement ce que je cherchais pour remplacer SQLAlchemy dans mes projets async. Migré en un week-end.',
     'b2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003', 'review'),

    ('c3000000-0000-0000-0000-000000000003',
     'Est-ce que halfORM supporte les schémas multiples dans la même base ?',
     'b2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000004', 'question'),

    -- post 2 (Litestar vs FastAPI) — 3 commentaires
    ('c3000000-0000-0000-0000-000000000004',
     'J''aurais aimé un benchmark de performances entre les deux, mais la comparaison des APIs est utile.',
     'b2000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000005', 'comment'),

    ('c3000000-0000-0000-0000-000000000005',
     '★★★★☆ — Bonne synthèse, mais le point sur les guards Litestar mériterait un article dédié.',
     'b2000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000001', 'review'),

    ('c3000000-0000-0000-0000-000000000006',
     'Le typage fort de Litestar est vraiment agréable quand on vient de TypeScript.',
     'b2000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000003', 'comment'),

    -- post 3 (Svelte 5 runes) — 2 commentaires
    ('c3000000-0000-0000-0000-000000000007',
     '★★★★★ — Les runes clarifient enfin la distinction entre état local et état partagé. Article très clair.',
     'b2000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000002', 'review'),

    ('c3000000-0000-0000-0000-000000000008',
     'La migration depuis Svelte 4 est-elle documentée par la communauté quelque part ?',
     'b2000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000004', 'question'),

    -- post 4 (PostgreSQL FTS) — 2 commentaires
    ('c3000000-0000-0000-0000-000000000009',
     'N''oubliez pas unaccent() pour les recherches insensibles aux accents en français.',
     'b2000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000001', 'comment'),

    ('c3000000-0000-0000-0000-000000000010',
     '★★★☆☆ — Contenu solide mais les exemples auraient gagné à utiliser des données réelles plutôt que du lorem ipsum.',
     'b2000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000005', 'review'),

    -- post 5 (UUID v4 vs v7) — 2 commentaires
    ('c3000000-0000-0000-0000-000000000011',
     '★★★★★ — Enfin un article qui explique la fragmentation B-Tree clairement. Je bascule sur UUID v7 dès demain.',
     'b2000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000002', 'review'),

    ('c3000000-0000-0000-0000-000000000012',
     'ULID est aussi une alternative intéressante si vous voulez rester sur des identifiants lisibles.',
     'b2000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000003', 'comment'),

    -- post 6 (Asyncio) — 2 commentaires
    ('c3000000-0000-0000-0000-000000000013',
     'Le piège de gather() avec des exceptions partielles m''a coûté deux jours de debug. Merci pour la mise en garde.',
     'b2000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000004', 'comment'),

    ('c3000000-0000-0000-0000-000000000014',
     '★★★★☆ — Très utile. J''ajouterais la gestion des signaux SIGTERM pour un shutdown propre en production.',
     'b2000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000005', 'review'),

    -- post 7 (Générer une API REST) — 3 commentaires
    ('c3000000-0000-0000-0000-000000000015',
     'CRUD_ACCESS est une idée brillante : les droits au plus près du modèle, pas dans une couche middleware séparée.',
     'b2000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000001', 'comment'),

    ('c3000000-0000-0000-0000-000000000016',
     '★★★★★ — J''ai généré une API complète en 20 minutes. Bluffant.',
     'b2000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000003', 'review'),

    ('c3000000-0000-0000-0000-000000000017',
     'Est-ce que --fastapi génère aussi les schémas Pydantic pour la doc OpenAPI ?',
     'b2000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000004', 'comment'),

    -- post 9 (Pydantic v2) — 2 commentaires
    ('c3000000-0000-0000-0000-000000000018',
     'La réécriture en Rust de pydantic-core change vraiment la donne sur les volumes importants.',
     'b2000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000002', 'comment'),

    ('c3000000-0000-0000-0000-000000000019',
     'Pensez à `model_config = ConfigDict(from_attributes=True)` pour la compatibilité ORM.',
     'b2000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000005', 'comment'),

    -- post 10 (TypeScript strict) — 1 commentaire
    ('c3000000-0000-0000-0000-000000000020',
     'noUncheckedIndexedAccess est douloureux au départ mais sauve de nombreux bugs à l''exécution.',
     'b2000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000001', 'comment');

-- ── user → role assignments ───────────────────────────────────────────────────

INSERT INTO "half_orm_meta.api".user_role (user_id, role_name) VALUES
    ('a0000000-0000-0000-0000-000000000000', 'admin')
ON CONFLICT DO NOTHING;

COMMIT;

-- Vérification rapide
SELECT 'authors' AS table_name, COUNT(*) FROM "half_orm_meta.identity"."user"
UNION ALL
SELECT 'posts',    COUNT(*) FROM blog.post
UNION ALL
SELECT 'comments', COUNT(*) FROM blog.comment
UNION ALL
SELECT 'reviews',  COUNT(*) FROM blog.comment WHERE comment_type = 'review';
