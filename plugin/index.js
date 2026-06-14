import { tool } from "@opencode-ai/plugin/tool";
import { randomUUID } from "node:crypto";
import { mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const DATA_DIR = process.env.MEMORY_STORE_DIR || join(homedir(), ".memory-store");
const DB_PATH = join(DATA_DIR, "store.db");

let db = null;

function getDb() {
  if (db) return db;
  mkdirSync(DATA_DIR, { recursive: true });
  const Database = require("better-sqlite3");
  db = new Database(DB_PATH);
  db.pragma("journal_mode = WAL");
  db.exec(`
    CREATE TABLE IF NOT EXISTS entities (
      id TEXT PRIMARY KEY,
      type TEXT NOT NULL DEFAULT 'memory',
      name TEXT NOT NULL DEFAULT '',
      text TEXT NOT NULL DEFAULT '',
      category TEXT NOT NULL DEFAULT 'general',
      scope TEXT NOT NULL DEFAULT 'global',
      importance REAL NOT NULL DEFAULT 0.5,
      tags TEXT NOT NULL DEFAULT '[]',
      data TEXT NOT NULL DEFAULT '{}',
      source TEXT DEFAULT 'manual',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
      name, text, category, tags,
      content='entities',
      content_rowid='rowid'
    );
    CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
      INSERT INTO entities_fts(rowid, name, text, category, tags)
      VALUES (new.rowid, new.name, new.text, new.category, new.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
      INSERT INTO entities_fts(entities_fts, rowid, name, text, category, tags)
      VALUES ('delete', old.rowid, old.name, old.text, old.category, old.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
      INSERT INTO entities_fts(entities_fts, rowid, name, text, category, tags)
      VALUES ('delete', old.rowid, old.name, old.text, old.category, old.tags);
      INSERT INTO entities_fts(rowid, name, text, category, tags)
      VALUES (new.rowid, new.name, new.text, new.category, new.tags);
    END
  `);
  for (const col of ["type", "scope", "category", "importance"]) {
    db.exec(`CREATE INDEX IF NOT EXISTS idx_entities_${col} ON entities(${col})`);
  }
  // Rebuild FTS for existing data if needed
  try {
    const hasEntities = db.prepare("SELECT COUNT(*) as c FROM entities").get().c;
    const hasFts = db.prepare("SELECT COUNT(*) as c FROM entities_fts").get().c;
    if (hasEntities > 0 && hasFts === 0) {
      db.exec("INSERT INTO entities_fts(entities_fts) VALUES('rebuild')");
    }
  } catch (_) {}
  return db;
}

function now() { return new Date().toISOString(); }

function jsonCol(col) {
  try { return JSON.parse(col); } catch { return col === "data" ? {} : []; }
}

function ftsQuery(text) {
  if (!text) return "";
  return text.match(/[-\w]+/g)?.join(" AND ") || "";
}

function buildRecall(args) {
  const d = getDb();
  let useFts = false, sql, params;
  if (args.query) {
    const fq = ftsQuery(args.query);
    if (fq) {
      useFts = true;
      sql = ["SELECT e.* FROM entities e JOIN entities_fts fts ON e.rowid = fts.rowid WHERE entities_fts MATCH ?"];
      params = [fq];
    }
  }
  if (!useFts) {
    sql = ["SELECT * FROM entities WHERE 1=1"];
    params = [];
    if (args.query) {
      const l = `%${args.query}%`;
      sql.push("AND (name LIKE ? OR text LIKE ? OR category LIKE ? OR tags LIKE ?)");
      params.push(l, l, l, l);
    }
  }
  if (args.type) { sql.push(useFts ? "AND e.type = ?" : "AND type = ?"); params.push(args.type); }
  if (args.scope) { sql.push(useFts ? "AND e.scope = ?" : "AND scope = ?"); params.push(args.scope); }
  if (args.category) { sql.push(useFts ? "AND e.category = ?" : "AND category = ?"); params.push(args.category); }
  sql.push(useFts ? "ORDER BY e.importance DESC, e.updated_at DESC" : "ORDER BY importance DESC, updated_at DESC");
  sql.push("LIMIT ?");
  params.push(args.limit || 10);
  try { return d.prepare(sql.join(" ")).all(...params); }
  catch { return []; }
}

function formatRows(rows, label) {
  if (!rows.length) return label ? `No ${label} found.` : "No results found.";
  const lines = [label ? `Total: ${rows.length} ${label}:\n` : `Found ${rows.length} result(s):\n`];
  rows.forEach((r, i) => {
    const n = r.name ? ` [${r.name}]` : "";
    lines.push(`${i + 1}. (${r.type})${n} ${(r.text || "").substring(0, 120)}`);
    lines.push(`   Scope: ${r.scope} | Cat: ${r.category} | Imp: ${r.importance}`);
    const tags = jsonCol(r.tags);
    if (tags.length) lines.push(`   Tags: ${tags.join(", ")}`);
    try {
      const data = typeof r.data === "string" ? JSON.parse(r.data) : (r.data || {});
      if (data.path) {
        const exists = existsSync(data.path);
        lines.push(`   Path: ${data.path}${exists ? "" : " ⚠ PATH DOES NOT EXIST"}`);
      }
    } catch (_) {}
    lines.push("");
  });
  return lines.join("\n");
}

const ENTITY_TYPES_OPT = tool.schema.string().optional().describe("Entity type filter");
const ENTITY_TYPE_REQ = tool.schema.string().describe("Entity type");

const plugin = async () => ({
  tool: {
    memory_store: tool({
      description: "Store a memory/fact into long-term storage. Use this AFTER you learn something worth remembering — user preferences, project decisions, gotchas, architecture choices, config hurdles. Always set a scope so memories don't leak between projects.",
      args: {
        type: ENTITY_TYPE_REQ,
        name: tool.schema.string().optional().describe("Short label for this entity"),
        text: tool.schema.string().describe("The content to remember"),
        category: tool.schema.string().optional().describe("Grouping category (e.g. architecture, preference, gotcha, config)"),
        scope: tool.schema.string().optional().describe("Isolation scope: 'global' for universal knowledge, 'project:<name>' for project-specific, 'user:<name>' for per-user. Default: global"),
        importance: tool.schema.number().min(0).max(1).optional().describe("How critical this is: 0.9+ = essential (API keys, arch decisions), 0.5-0.8 = useful (patterns, preferences), 0.1-0.4 = nice-to-know"),
        tags: tool.schema.array(tool.schema.string()).optional().describe("Tags for filtering"),
        data: tool.schema.object({}).optional().describe("Additional structured data as JSON"),
      },
      async execute(args, _ctx) {
        try {
          const d = getDb();
          const id = randomUUID();
          const ts = now();
          d.prepare(`INSERT INTO entities (id,type,name,text,category,scope,importance,tags,data,source,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`).run(
            id, args.type, args.name || "", args.text || "", args.category || "general",
            args.scope || "global", args.importance ?? 0.5,
            JSON.stringify(args.tags || []), JSON.stringify(args.data || {}),
            "plugin", ts, ts
          );
          return `Stored ${args.type}: ${id}\nName: ${args.name || "(none)"}\nScope: ${args.scope || "global"}`;
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_recall: tool({
      description: "BEFORE answering a user's question, call this to search your memory for relevant context. You have FTS5 full-text search — query for project names, decisions, preferences, or any keyword. Always scope to the active project when applicable. This is how you avoid cold starts.",
      args: {
        query: tool.schema.string().describe("Search keywords — will match against names, text, categories, and tags"),
        type: ENTITY_TYPES_OPT,
        scope: tool.schema.string().optional().describe("Scope filter — e.g. 'project:my-app' to only search within a project"),
        category: tool.schema.string().optional().describe("Category filter"),
        limit: tool.schema.number().min(1).max(100).optional().describe("Max results, default 10"),
      },
      async execute(args, _ctx) { try { return formatRows(buildRecall(args)); } catch (e) { return `Error: ${e.message || String(e)}`; } },
    }),

    memory_list: tool({
      description: "List stored entities. Use to browse what you know about a scope or category when you're not sure what keywords to search for.",
      args: {
        type: ENTITY_TYPES_OPT,
        scope: tool.schema.string().optional().describe("Scope filter — e.g. 'project:my-app' to see everything about a project"),
        category: tool.schema.string().optional().describe("Category filter"),
        limit: tool.schema.number().min(1).max(100).optional().describe("Max results, default 50"),
      },
      async execute(args, _ctx) {
        try {
          const d = getDb();
          const sql = ["SELECT id,type,name,text,scope,category,importance FROM entities WHERE 1=1"];
          const p = [];
          if (args.type) { sql.push("AND type = ?"); p.push(args.type); }
          if (args.scope) { sql.push("AND scope = ?"); p.push(args.scope); }
          if (args.category) { sql.push("AND category = ?"); p.push(args.category); }
          sql.push("ORDER BY updated_at DESC LIMIT ?"); p.push(args.limit || 50);
          return formatRows(d.prepare(sql.join(" ")).all(...p), args.type || "entities");
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_get: tool({
      description: "Get the full details of a specific entity by its ID. Use this after a recall or list returns a match you want to inspect completely.",
      args: { entityId: tool.schema.string().describe("Entity ID") },
      async execute(args, _ctx) {
        try {
          const r = getDb().prepare("SELECT * FROM entities WHERE id = ?").get(args.entityId);
          if (!r) return "Entity not found.";
          return [
            `ID:   ${r.id}`, `Type: ${r.type}`, `Name: ${r.name || "(none)"}`,
            `Text: ${r.text}`, `Cat:  ${r.category}`, `Scope: ${r.scope}`,
            `Imp:  ${r.importance}`, `Tags: ${r.tags}`,
            `Data: ${JSON.stringify(jsonCol(r.data), null, 2)}`,
            `Src:  ${r.source}`, `Created: ${r.created_at}`, `Updated: ${r.updated_at}`,
          ].join("\n");
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_update: tool({
      description: "Update an existing entity when a fact changes. Prefer this over storing duplicate entries — it keeps the memory clean and avoids stale data.",
      args: {
        entityId: tool.schema.string().describe("Entity ID to update"),
        name: tool.schema.string().optional(),
        text: tool.schema.string().optional(),
        category: tool.schema.string().optional(),
        importance: tool.schema.number().min(0).max(1).optional(),
        scope: tool.schema.string().optional(),
        tags: tool.schema.array(tool.schema.string()).optional(),
        data: tool.schema.object({}).optional(),
      },
      async execute(args, _ctx) {
        try {
          const d = getDb(); const sets = []; const p = [];
          if (args.name !== undefined) { sets.push("name = ?"); p.push(args.name); }
          if (args.text !== undefined) { sets.push("text = ?"); p.push(args.text); }
          if (args.category !== undefined) { sets.push("category = ?"); p.push(args.category); }
          if (args.importance !== undefined) { sets.push("importance = ?"); p.push(args.importance); }
          if (args.scope !== undefined) { sets.push("scope = ?"); p.push(args.scope); }
          if (args.tags !== undefined) { sets.push("tags = ?"); p.push(JSON.stringify(args.tags)); }
          if (args.data !== undefined) { sets.push("data = ?"); p.push(JSON.stringify(args.data)); }
          if (!sets.length) return "No fields to update.";
          sets.push("updated_at = ?"); p.push(now()); p.push(args.entityId);
          const info = d.prepare(`UPDATE entities SET ${sets.join(", ")} WHERE id = ?`).run(...p);
          return info.changes > 0 ? "Updated." : "Not found.";
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_forget: tool({
      description: "Delete obsolete or incorrect memories. Use when a stored fact is no longer true or was stored by mistake.",
      args: {
        entityId: tool.schema.string().optional().describe("Delete specific ID"),
        query: tool.schema.string().optional().describe("Delete matching content"),
        scope: tool.schema.string().optional().describe("Delete all in this scope"),
        type: ENTITY_TYPES_OPT,
      },
      async execute(args, _ctx) {
        try {
          if (!args.entityId && !args.query && !args.scope && !args.type)
            return "Error: provide at least one filter (entityId, query, scope, or type)";
          const d = getDb(); const sql = ["DELETE FROM entities WHERE 1=1"]; const p = [];
          if (args.entityId) { sql.push("AND id = ?"); p.push(args.entityId); }
          if (args.query) { const l = `%${args.query}%`; sql.push("AND (name LIKE ? OR text LIKE ?)"); p.push(l, l); }
          if (args.scope) { sql.push("AND scope = ?"); p.push(args.scope); }
          if (args.type) { sql.push("AND type = ?"); p.push(args.type); }
          return `Deleted ${d.prepare(sql.join(" ")).run(...p).changes}.`;
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_stats: tool({
      description: "Get memory store statistics by type/category/scope.",
      args: {},
      async execute(_args, _ctx) {
        try {
          const d = getDb();
          const total = d.prepare("SELECT COUNT(*) as c FROM entities").get().c;
          const byType = d.prepare("SELECT type, COUNT(*) as c FROM entities GROUP BY type ORDER BY type").all();
          const byCat = d.prepare("SELECT category, COUNT(*) as c FROM entities GROUP BY category ORDER BY category").all();
          const byScope = d.prepare("SELECT scope, COUNT(*) as c FROM entities GROUP BY scope ORDER BY scope").all();
          const range = d.prepare("SELECT MIN(created_at) as oldest, MAX(updated_at) as newest FROM entities").get();
          return [
            "Memory Statistics", "=".repeat(17), `Total: ${total}\n`,
            "By type:", ...byType.map(r => `  ${r.type}: ${r.c}`),
            "\nBy category:", ...byCat.map(r => `  ${r.category}: ${r.c}`),
            "\nBy scope:", ...byScope.map(r => `  ${r.scope}: ${r.c}`),
            `\nRange: ${range?.oldest || "N/A"} to ${range?.newest || "N/A"}`,
          ].join("\n");
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_debug: tool({
      description: "Call this on session start to verify the memory store is available. If it fails, the other memory_* tools won't work either.",
      args: {},
      async execute(_args, _ctx) {
        try {
          return `opencode-memory-store plugin OK — ${getDb().prepare("SELECT COUNT(*) as c FROM entities").get().c} entities in SQLite`;
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),
  },
});

export default plugin;
