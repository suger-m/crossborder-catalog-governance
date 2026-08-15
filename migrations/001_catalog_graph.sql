CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  external_id TEXT NOT NULL,
  title TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skus (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  product_id TEXT NOT NULL,
  external_id TEXT NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS product_facts (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  product_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  value_json TEXT NOT NULL,
  state TEXT NOT NULL,
  confidence REAL NOT NULL,
  source_document_id TEXT NOT NULL,
  evidence_text TEXT NOT NULL,
  evidence_location TEXT NOT NULL,
  taxonomy_node_id TEXT NOT NULL DEFAULT '',
  taxonomy_version TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS graph_nodes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  node_type TEXT NOT NULL,
  state TEXT NOT NULL,
  version INTEGER NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_edges (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  source_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  state TEXT NOT NULL,
  version INTEGER NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_evidence (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  subject_id TEXT NOT NULL,
  source_document_id TEXT NOT NULL,
  evidence_text TEXT NOT NULL,
  evidence_location TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_versions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  product_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(product_id, version)
);
CREATE TABLE IF NOT EXISTS listings (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL DEFAULT '',
  process_task_id TEXT NOT NULL DEFAULT '',
  product_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  version INTEGER NOT NULL,
  derived_from_product_version INTEGER NOT NULL,
  platform_rule_version TEXT NOT NULL,
  status TEXT NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_products (
  task_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  project_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  PRIMARY KEY(task_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_product_facts_product ON product_facts(product_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_listings_product ON listings(product_id, platform);
CREATE INDEX IF NOT EXISTS idx_task_products_task ON task_products(task_id);
