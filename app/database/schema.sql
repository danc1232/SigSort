CREATE TYPE {SCHEMA}."feed_types" AS ENUM (
  'aggregator',
  'blog',
  'vendor',
  'news',
  'gov',
  'org'
);

CREATE TABLE {SCHEMA}."locations" (
  id        varchar(3) PRIMARY KEY,
  name      varchar,
  latitude  decimal(5,2),
  longitude decimal(5,2)
);

CREATE TABLE {SCHEMA}."feeds" (
  id                  serial PRIMARY KEY,
  name                varchar NOT NULL,
  url                 varchar NOT NULL,
  type                {SCHEMA}."feed_types",
  location            varchar(3),
  status              boolean DEFAULT TRUE,
  updated             timestamptz DEFAULT '1970-01-01T00:00:00+00:00',
  content_hash        bigint,
  last_fail           timestamptz,
  fail_reason         varchar,
  fail_count          int DEFAULT 0,
  deep_parse_enabled  boolean DEFAULT FALSE,
  content_perimeter   varchar,
  title_field         varchar,
  text_fields         varchar[]
);

CREATE TABLE {SCHEMA}."rss_entries" (
  id            bigint PRIMARY KEY,
  title         varchar NOT NULL,
  link          varchar,
  summary       varchar NOT NULL,
  pub_date      timestamptz,
  entities      varchar[],
  keywords      varchar[],
  vulns         varchar[],
  full_text     varchar,
  feed          int NOT NULL
);

ALTER TABLE {SCHEMA}."feeds" ADD FOREIGN KEY (location) REFERENCES {SCHEMA}."locations" (id);

ALTER TABLE {SCHEMA}."rss_entries" ADD FOREIGN KEY (feed) REFERENCES {SCHEMA}."feeds" (id);

CREATE USER grafanareader WITH PASSWORD 'password';

GRANT USAGE ON SCHEMA {SCHEMA} TO grafanareader;

GRANT SELECT ON {SCHEMA}.locations TO grafanareader;
GRANT SELECT ON {SCHEMA}.feeds TO grafanareader;
GRANT SELECT ON {SCHEMA}.rss_entries TO grafanareader;
GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO grafanareader;

ALTER ROLE grafanareader SET search_path = '{SCHEMA}';
