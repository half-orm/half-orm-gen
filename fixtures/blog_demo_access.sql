--
-- PostgreSQL database dump
--

\restrict bdQ30moMhypUjBuPQraFNulyNviA8wzfaFT7rnLHtge3Eh7EOXKvFk8lS4U33cY

-- Dumped from database version 17.10 (Debian 17.10-0+deb13u1)
-- Dumped by pg_dump version 17.10 (Debian 17.10-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: access; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".access VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'anonymous', 'blog', 'comment', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('6e833ab2-fd72-4b25-bdef-c020c489b7e0', 'anonymous', 'blog', 'comment_type', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'anonymous', 'blog', 'post', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('d3b60f38-a19b-4174-974b-a8c83a4bc9a2', 'anonymous', 'half_orm_meta.identity', 'user', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('dec2bf37-7807-4e72-8835-dff7af019b43', 'connected', 'blog', 'post', 'POST') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'connected', 'half_orm_meta.identity', 'user', 'POST') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_fk_auto; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('008cdf1a-b35a-4b31-a1e9-d4650930254c', 'dec2bf37-7807-4e72-8835-dff7af019b43', 'author_id', 'select') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('92673a8f-dec3-4975-ad47-4a4cb3ec9edf', 'c038fc31-ead8-492e-a897-f49dc4364e8e', 'origin_peer_id', 'select') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_in; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_in VALUES ('dec2bf37-7807-4e72-8835-dff7af019b43', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('dec2bf37-7807-4e72-8835-dff7af019b43', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('dec2bf37-7807-4e72-8835-dff7af019b43', 'published') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('dec2bf37-7807-4e72-8835-dff7af019b43', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'email') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'origin_peer_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'name') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_out; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_out VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'comment_type') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'post_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('6e833ab2-fd72-4b25-bdef-c020c489b7e0', 'name') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'published') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('d3b60f38-a19b-4174-974b-a8c83a4bc9a2', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('d3b60f38-a19b-4174-974b-a8c83a4bc9a2', 'name') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('dec2bf37-7807-4e72-8835-dff7af019b43', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'password_hash') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'email') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'origin_peer_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'last_seen_at') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'first_seen_at') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('c038fc31-ead8-492e-a897-f49dc4364e8e', 'name') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_searchable; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'content', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('7a3507bc-5f55-4bc5-83e4-9a9f1798f846', 'comment_type', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('6e833ab2-fd72-4b25-bdef-c020c489b7e0', 'name', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'title', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('2001c0b8-6314-4863-b365-53856ea052d3', 'content', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('d3b60f38-a19b-4174-974b-a8c83a4bc9a2', 'name', NULL) ON CONFLICT DO NOTHING;


--
-- Data for Name: user_role; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".user_role VALUES ('a0000000-0000-0000-0000-000000000000', 'admin') ON CONFLICT DO NOTHING;


--
-- PostgreSQL database dump complete
--

\unrestrict bdQ30moMhypUjBuPQraFNulyNviA8wzfaFT7rnLHtge3Eh7EOXKvFk8lS4U33cY

INSERT INTO "half_orm_meta.api".access_filter (access_id, filter_id) SELECT '2001c0b8-6314-4863-b365-53856ea052d3'::uuid, f.id FROM "half_orm_meta.api".filter f WHERE f.schema_name='blog' AND f.table_name='post' AND f.name='published_posts' ON CONFLICT DO NOTHING;
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'blog' AND table_name = 'comment' AND column_name = 'content';
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'blog' AND table_name = 'comment_type' AND column_name = 'name';
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'blog' AND table_name = 'post' AND column_name = 'title';
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'half_orm_meta.identity' AND table_name = 'user' AND column_name = 'name';
