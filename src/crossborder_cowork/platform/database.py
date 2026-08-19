from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


PLATFORM_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  objective TEXT NOT NULL,
  status TEXT NOT NULL,
  current_step TEXT NOT NULL DEFAULT '',
  input_json TEXT NOT NULL DEFAULT '{}',
  result_json TEXT NOT NULL DEFAULT '{}',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id)
);
CREATE TABLE IF NOT EXISTS project_materials (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  file_name TEXT NOT NULL,
  absolute_path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  origin TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id),
  UNIQUE(project_id, sha256)
);
CREATE INDEX IF NOT EXISTS idx_project_materials_project_created
  ON project_materials(project_id, created_at);
CREATE TABLE IF NOT EXISTS task_materials (
  task_id TEXT NOT NULL,
  material_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(task_id, material_id),
  FOREIGN KEY(task_id) REFERENCES tasks(id),
  FOREIGN KEY(material_id) REFERENCES project_materials(id)
);
CREATE INDEX IF NOT EXISTS idx_task_materials_task_sequence
  ON task_materials(task_id, sequence);
CREATE TABLE IF NOT EXISTS task_steps (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  external_id TEXT NOT NULL DEFAULT '',
  sequence INTEGER NOT NULL,
  worker_name TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  result_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT,
  completed_at TEXT,
  FOREIGN KEY(task_id) REFERENCES tasks(id)
);
CREATE TABLE IF NOT EXISTS task_step_dependencies (
  step_id TEXT NOT NULL,
  depends_on_step_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(step_id, depends_on_step_id),
  FOREIGN KEY(step_id) REFERENCES task_steps(id),
  FOREIGN KEY(depends_on_step_id) REFERENCES task_steps(id)
);
CREATE INDEX IF NOT EXISTS idx_task_step_dependencies_upstream
  ON task_step_dependencies(depends_on_step_id);
CREATE TABLE IF NOT EXISTS events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS product_events (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  protocol_name TEXT NOT NULL,
  protocol_version INTEGER NOT NULL,
  action TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_event_id TEXT NOT NULL,
  source_ordinal INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(task_id, sequence),
  UNIQUE(task_id, source_kind, source_event_id, source_ordinal, action)
);
CREATE INDEX IF NOT EXISTS idx_product_events_task_sequence
  ON product_events(task_id, sequence);
CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  project_id TEXT NOT NULL DEFAULT '',
  process_task_id TEXT NOT NULL DEFAULT '',
  worker_name TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  title TEXT NOT NULL,
  file_name TEXT NOT NULL,
  absolute_path TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  dependency_ids_json TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_resources (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  logical_key TEXT NOT NULL,
  owner_worker_name TEXT NOT NULL,
  source_task_id TEXT NOT NULL,
  source_step_id TEXT NOT NULL DEFAULT '',
  storage_kind TEXT NOT NULL,
  storage_ref TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(project_id) REFERENCES projects(id),
  FOREIGN KEY(source_task_id) REFERENCES tasks(id),
  UNIQUE(project_id, resource_type, logical_key, version)
);
CREATE INDEX IF NOT EXISTS idx_project_resources_lookup
  ON project_resources(project_id, resource_type, status, logical_key, version DESC);
CREATE INDEX IF NOT EXISTS idx_project_resources_source_step
  ON project_resources(source_step_id, created_at);
CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  approval_type TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  decision_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  decided_at TEXT
);
"""


class _ClosingConnection(sqlite3.Connection):
    """Make ``with Database.connect()`` release Windows file locks after commit."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Database:
    def __init__(self, path: Path, migrations_dir: Path | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrations_dir = migrations_dir
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False, factory=_ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(PLATFORM_SCHEMA)
            self._ensure_platform_columns(conn)
            if self.migrations_dir and self.migrations_dir.exists():
                for path in sorted(self.migrations_dir.glob("*.sql")):
                    conn.executescript(path.read_text(encoding="utf-8"))
            self._ensure_catalog_columns(conn)
            self._ensure_indexes(conn)

    @staticmethod
    def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    @classmethod
    def _ensure_column(cls, conn: sqlite3.Connection, table: str, definition: str) -> None:
        name = definition.split()[0]
        if name not in cls._column_names(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")

    @classmethod
    def _ensure_platform_columns(cls, conn: sqlite3.Connection) -> None:
        # ``task_steps.id`` is a platform-owned primary key.  AgentTeams
        # phase/task identifiers (for example ``catalog``) are only stable
        # inside one external task and therefore live in ``external_id``.
        # Existing databases predate this boundary; preserve their local IDs
        # and use those IDs as the historical external identity.
        cls._ensure_column(conn, "task_steps", "external_id TEXT NOT NULL DEFAULT ''")
        conn.execute(
            "UPDATE task_steps SET external_id=id WHERE external_id=''"
        )
        cls._ensure_column(conn, "artifacts", "project_id TEXT NOT NULL DEFAULT ''")
        cls._ensure_column(conn, "artifacts", "process_task_id TEXT NOT NULL DEFAULT ''")
        conn.execute(
            """UPDATE artifacts SET project_id=COALESCE(
                   (SELECT project_id FROM tasks WHERE tasks.id=artifacts.task_id), '')
               WHERE project_id=''"""
        )

    @classmethod
    def _ensure_catalog_columns(cls, conn: sqlite3.Connection) -> None:
        for table in (
            "products", "skus", "product_facts", "graph_nodes", "graph_edges",
            "graph_evidence", "graph_versions", "listings", "task_products",
        ):
            cls._ensure_column(conn, table, "project_id TEXT NOT NULL DEFAULT ''")
        cls._ensure_column(conn, "listings", "process_task_id TEXT NOT NULL DEFAULT ''")

        conn.execute(
            """UPDATE task_products SET project_id=COALESCE(
                   (SELECT project_id FROM tasks WHERE tasks.id=task_products.task_id), '')
               WHERE project_id=''"""
        )
        for table in ("products", "skus", "product_facts", "listings"):
            conn.execute(
                f"""UPDATE {table} SET project_id=COALESCE(
                       (SELECT tp.project_id FROM task_products tp
                        WHERE tp.product_id={table}.product_id LIMIT 1), '')
                   WHERE project_id=''"""
                if table != "products"
                else """UPDATE products SET project_id=COALESCE(
                       (SELECT tp.project_id FROM task_products tp
                        WHERE tp.product_id=products.id LIMIT 1), '')
                   WHERE project_id=''"""
            )

    @staticmethod
    def _ensure_indexes(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_products_project ON products(project_id, title);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_task_steps_external
              ON task_steps(task_id, external_id) WHERE external_id <> '';
            CREATE INDEX IF NOT EXISTS idx_task_steps_task_external
              ON task_steps(task_id, external_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_project_created ON artifacts(project_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_artifacts_process_task ON artifacts(process_task_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_skus_project_product ON skus(project_id, product_id);
            CREATE INDEX IF NOT EXISTS idx_product_facts_project_product ON product_facts(project_id, product_id);
            CREATE INDEX IF NOT EXISTS idx_listings_project_platform ON listings(project_id, platform, product_id);
            CREATE INDEX IF NOT EXISTS idx_graph_nodes_project ON graph_nodes(project_id, node_type);
            CREATE INDEX IF NOT EXISTS idx_graph_edges_project_source ON graph_edges(project_id, source_id);
            CREATE INDEX IF NOT EXISTS idx_task_products_project ON task_products(project_id, task_id);
            """
        )

    def execute(self, sql: str, params: Iterable[object] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, tuple(params))

    def fetchone(self, sql: str, params: Iterable[object] = ()) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: Iterable[object] = ()) -> list[dict]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
