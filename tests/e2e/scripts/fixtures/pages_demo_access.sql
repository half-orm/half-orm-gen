--
-- PostgreSQL database dump
--

\restrict yEKdQ73rX03FG3MvF6onfWHvYu9sw5wIOODgRfbZ2Ujol11zQq4DDhbIysSL7Gc

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

INSERT INTO "half_orm_meta.api".access VALUES ('49e2c77f-5e37-478a-9b9b-9e03d2ec92a7', 'anonymous', 'wiki', 'page', 'GET') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'connected', 'wiki', 'page', 'POST') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('d78f5c19-31b8-4cfa-9ceb-c7c3325640a9', 'page_author', 'wiki', 'page', 'PUT') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".access VALUES ('bd243357-2502-4992-aa02-1c27fa226043', 'page_author', 'wiki', 'page', 'DELETE') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_fk_auto; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_fk_auto VALUES ('bac56e4b-556a-444d-b39b-ef2162d44cb8', 'dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'author_id', 'connected_user') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_in; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_in VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('d78f5c19-31b8-4cfa-9ceb-c7c3325640a9', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_in VALUES ('d78f5c19-31b8-4cfa-9ceb-c7c3325640a9', 'title') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_out; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_out VALUES ('49e2c77f-5e37-478a-9b9b-9e03d2ec92a7', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('49e2c77f-5e37-478a-9b9b-9e03d2ec92a7', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('49e2c77f-5e37-478a-9b9b-9e03d2ec92a7', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('49e2c77f-5e37-478a-9b9b-9e03d2ec92a7', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('dff548c2-d8d6-4cf2-8f36-0de099eb9454', 'title') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('d78f5c19-31b8-4cfa-9ceb-c7c3325640a9', 'id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('d78f5c19-31b8-4cfa-9ceb-c7c3325640a9', 'author_id') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('d78f5c19-31b8-4cfa-9ceb-c7c3325640a9', 'content') ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_out VALUES ('d78f5c19-31b8-4cfa-9ceb-c7c3325640a9', 'title') ON CONFLICT DO NOTHING;


--
-- Data for Name: field_access_searchable; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('49e2c77f-5e37-478a-9b9b-9e03d2ec92a7', 'content', NULL) ON CONFLICT DO NOTHING;
INSERT INTO "half_orm_meta.api".field_access_searchable VALUES ('49e2c77f-5e37-478a-9b9b-9e03d2ec92a7', 'title', NULL) ON CONFLICT DO NOTHING;


--
-- Data for Name: user_role; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".user_role VALUES ('a0000000-0000-0000-0000-000000000000', 'admin') ON CONFLICT DO NOTHING;


--
-- PostgreSQL database dump complete
--

\unrestrict yEKdQ73rX03FG3MvF6onfWHvYu9sw5wIOODgRfbZ2Ujol11zQq4DDhbIysSL7Gc

UPDATE "half_orm_meta.api".field SET label_order = 0 WHERE schema_name = 'wiki' AND table_name = 'page' AND column_name = 'title';
