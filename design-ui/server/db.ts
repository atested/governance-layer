import { DatabaseSync } from "node:sqlite";
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const defaultDataDir = path.resolve(__dirname, "..", ".data");
const migrationsDir = path.resolve(__dirname, "migrations");

export type DesignDatabase = DatabaseSync;

export function defaultDatabasePath() {
  return path.join(defaultDataDir, "design-ui.sqlite");
}

export function openDatabase(dbPath = defaultDatabasePath()) {
  const directory = path.dirname(dbPath);
  if (!existsSync(directory)) {
    mkdirSync(directory, { recursive: true });
  }

  const db = new DatabaseSync(dbPath);
  db.exec("PRAGMA foreign_keys = ON;");
  return db;
}

export function initializeDatabase(dbPath = defaultDatabasePath()) {
  const db = openDatabase(dbPath);
  runMigrations(db);
  return db;
}

export function runMigrations(db: DesignDatabase) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id TEXT PRIMARY KEY,
      appliedAt TEXT NOT NULL
    );
  `);

  const applied = new Set(
    db.prepare("SELECT id FROM schema_migrations").all().map((row) => String(row.id))
  );

  for (const migration of readdirSync(migrationsDir).filter((file) => file.endsWith(".sql")).sort()) {
    if (applied.has(migration)) continue;
    const sql = readFileSync(path.join(migrationsDir, migration), "utf8");
    db.exec("BEGIN;");
    try {
      db.exec(sql);
      db.prepare("INSERT INTO schema_migrations (id, appliedAt) VALUES (?, ?)").run(
        migration,
        new Date().toISOString()
      );
      db.exec("COMMIT;");
    } catch (error) {
      db.exec("ROLLBACK;");
      throw error;
    }
  }
}
