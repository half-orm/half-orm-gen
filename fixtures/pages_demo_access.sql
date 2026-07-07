--
-- PostgreSQL database dump
--

\restrict 5sGcoN1JjYe1HFwDpasiBpTcSMdwEkp2F2V01JEA7Zeu2foYicIe1DhRn1Cdi3r

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



--
-- Data for Name: field_access_fk_auto; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--



--
-- Data for Name: field_access_in; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--



--
-- Data for Name: field_access_out; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--



--
-- Data for Name: field_access_searchable; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--



--
-- Data for Name: user_role; Type: TABLE DATA; Schema: half_orm_meta.api; Owner: halftest
--

INSERT INTO "half_orm_meta.api".user_role VALUES ('a0000000-0000-0000-0000-000000000000', 'admin') ON CONFLICT DO NOTHING;


--
-- PostgreSQL database dump complete
--

\unrestrict 5sGcoN1JjYe1HFwDpasiBpTcSMdwEkp2F2V01JEA7Zeu2foYicIe1DhRn1Cdi3r

