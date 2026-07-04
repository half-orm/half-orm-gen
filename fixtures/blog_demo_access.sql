--
-- PostgreSQL database dump
--

\restrict J0ByJagdf7LziHradJZ033fNOdOKzhaQkeAnZOCjftWVGC0RX928euNxFsxzy5J

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

INSERT INTO "half_orm_meta.api".access VALUES ('f85a3172-50b1-4cc0-ac43-df65229a0771', 'anonymous', 'actor', 'user', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'anonymous', 'blog', 'post', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'connected', 'blog', 'comment', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'connected', 'blog', 'comment', 'POST') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('4755756b-815b-4d6f-84ab-c131059dc976', 'connected', 'blog', 'comment_type', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'connected', 'blog', 'post', 'POST') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('2c96c11e-1953-46f3-afd7-ffbfe71bfd2e', 'admin', 'actor', 'user', 'DELETE') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('cf478536-c611-4c14-bfe8-d86c667eeeff', 'admin', 'blog', 'comment', 'DELETE') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('57c953b4-6c4d-4fd3-8cee-4eb730ee97d0', 'admin', 'blog', 'comment_type', 'DELETE') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('2be1e251-84e1-4f4a-b396-b5db5b71be7a', 'admin', 'blog', 'post', 'DELETE') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('4cbb2a6f-692f-4d4e-ad93-8d3ef9283ef2', 'connected', 'actor', 'user', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('78950106-df0e-494a-b101-8fc2d17d58fb', 'connected', 'blog', 'post', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'post_author', 'blog', 'post', 'PUT') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('b4d6bb8b-0ea6-4eb1-9c6f-ce0a23d04bd8', 'post_author', 'blog', 'post', 'DELETE') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_fk_auto; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('663a288c-b5d2-4781-bc4e-2146c742a3a1', '950483a8-509c-4528-9cd9-69648107994f', 'post_id', 'context') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('c108da7b-c29f-4588-b57f-a3813d57cc3d', '950483a8-509c-4528-9cd9-69648107994f', 'author_id', 'connected_user') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('e675813d-109a-4136-b65c-0b6933a89293', '950483a8-509c-4528-9cd9-69648107994f', 'comment_type', 'select') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('404ec704-fbc2-4393-b13f-8d4f4398b57f', 'fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'author_id', 'connected_user') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('6bc5a593-6634-4a05-acac-25c047bc654a', 'f0238164-cc7d-4c91-a160-ebac673fc7b3', 'author_id', 'connected_user') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_in; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_in VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'comment_type') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'post_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'published') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'published') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'title') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_out; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_out VALUES ('f85a3172-50b1-4cc0-ac43-df65229a0771', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('f85a3172-50b1-4cc0-ac43-df65229a0771', 'name') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'published') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'comment_type') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'post_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'comment_type') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('950483a8-509c-4528-9cd9-69648107994f', 'post_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('4755756b-815b-4d6f-84ab-c131059dc976', 'name') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'published') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('fcb7972e-5670-4daf-b7f1-1c2af8b5167d', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('4cbb2a6f-692f-4d4e-ad93-8d3ef9283ef2', 'email') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'published') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('f0238164-cc7d-4c91-a160-ebac673fc7b3', 'title') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_searchable; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'content', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('279d1897-e942-4f0d-9c70-3259708b1acd', 'title', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'content', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('582d7cdf-bff6-4bfb-8f32-5950d88bffbd', 'comment_type', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('4755756b-815b-4d6f-84ab-c131059dc976', 'name', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('f85a3172-50b1-4cc0-ac43-df65229a0771', 'name', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('4cbb2a6f-692f-4d4e-ad93-8d3ef9283ef2', 'email', NULL) ON CONFLICT DO NOTHING;


--
-- Data for Name: user_role; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".user_role VALUES ('a0000000-0000-0000-0000-000000000000', 'admin') ON CONFLICT DO NOTHING;


--
-- PostgreSQL database dump complete
--

\unrestrict J0ByJagdf7LziHradJZ033fNOdOKzhaQkeAnZOCjftWVGC0RX928euNxFsxzy5J

INSERT INTO "half_orm_meta.api".access_filter (access_id, filter_id) SELECT '279d1897-e942-4f0d-9c70-3259708b1acd'::uuid, f.id FROM "half_orm_meta.api".filter f WHERE f.schema_name='blog' AND f.table_name='post' AND f.name='published_posts' ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access_filter (access_id, filter_id) SELECT '78950106-df0e-494a-b101-8fc2d17d58fb'::uuid, f.id FROM "half_orm_meta.api".filter f WHERE f.schema_name='blog' AND f.table_name='post' AND f.name='published_posts' ON CONFLICT DO NOTHING;
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'blog' AND table_name = 'post' AND column_name = 'title';
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'blog' AND table_name = 'comment' AND column_name = 'content';
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'blog' AND table_name = 'comment_type' AND column_name = 'name';
UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'actor' AND table_name = 'user' AND column_name = 'name';
