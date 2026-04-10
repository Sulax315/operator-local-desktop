-- Phase 1: separate application databases on shared Postgres (single superuser from POSTGRES_*).
CREATE DATABASE metabase;
CREATE DATABASE n8n;
