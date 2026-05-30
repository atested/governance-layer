CREATE TABLE IF NOT EXISTS schema_migrations (
  id TEXT PRIMARY KEY,
  appliedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  activeContextId TEXT,
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('operator', 'assistant', 'system')),
  content TEXT NOT NULL,
  sourceRefs TEXT NOT NULL DEFAULT '[]',
  createdAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_project_created
  ON chat_messages(projectId, createdAt);

CREATE TABLE IF NOT EXISTS discovery_items (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  discoveryType TEXT NOT NULL,
  state TEXT NOT NULL,
  createdFromMessageIds TEXT NOT NULL DEFAULT '[]',
  lineageEventIds TEXT NOT NULL DEFAULT '[]',
  tags TEXT NOT NULL DEFAULT '[]',
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_discovery_items_project
  ON discovery_items(projectId);

CREATE TABLE IF NOT EXISTS purpose_items (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  purposeType TEXT NOT NULL,
  state TEXT NOT NULL,
  createdFromMessageIds TEXT NOT NULL DEFAULT '[]',
  lineageEventIds TEXT NOT NULL DEFAULT '[]',
  tags TEXT NOT NULL DEFAULT '[]',
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_purpose_items_project
  ON purpose_items(projectId);

CREATE TABLE IF NOT EXISTS concepts (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  name TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  discoveryItemIds TEXT NOT NULL DEFAULT '[]',
  purposeItemIds TEXT NOT NULL DEFAULT '[]',
  relationshipIds TEXT NOT NULL DEFAULT '[]',
  maturity TEXT NOT NULL,
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_concepts_project
  ON concepts(projectId);

CREATE TABLE IF NOT EXISTS relationships (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  fromId TEXT NOT NULL,
  toId TEXT NOT NULL,
  type TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  createdAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_relationships_project
  ON relationships(projectId);

CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  proposalType TEXT NOT NULL,
  rationale TEXT NOT NULL DEFAULT '',
  proposedChanges TEXT NOT NULL,
  sourceMessageIds TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'rejected', 'modified')),
  createdAt TEXT NOT NULL,
  resolvedAt TEXT,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_proposals_project_status
  ON proposals(projectId, status);

CREATE TABLE IF NOT EXISTS lineage_events (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  subjectId TEXT NOT NULL,
  eventType TEXT NOT NULL,
  beforeValue TEXT,
  afterValue TEXT,
  messageIds TEXT NOT NULL DEFAULT '[]',
  proposalId TEXT,
  createdAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY (proposalId) REFERENCES proposals(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_lineage_events_project_subject
  ON lineage_events(projectId, subjectId, createdAt);

CREATE TABLE IF NOT EXISTS active_contexts (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  label TEXT NOT NULL,
  discoveryItemIds TEXT NOT NULL DEFAULT '[]',
  purposeItemIds TEXT NOT NULL DEFAULT '[]',
  conceptIds TEXT NOT NULL DEFAULT '[]',
  relationshipIds TEXT NOT NULL DEFAULT '[]',
  createdAt TEXT NOT NULL,
  updatedAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_active_contexts_project
  ON active_contexts(projectId);

CREATE TABLE IF NOT EXISTS spec_exports (
  id TEXT PRIMARY KEY,
  projectId TEXT NOT NULL,
  format TEXT NOT NULL CHECK (format IN ('markdown', 'json')),
  content TEXT NOT NULL,
  sourcePurposeItemIds TEXT NOT NULL DEFAULT '[]',
  sourceLineageEventIds TEXT NOT NULL DEFAULT '[]',
  createdAt TEXT NOT NULL,
  FOREIGN KEY (projectId) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_spec_exports_project
  ON spec_exports(projectId, createdAt);
