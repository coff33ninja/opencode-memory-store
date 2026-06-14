import { tool } from "@opencode-ai/plugin/tool";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const DATA_DIR = join(homedir(), ".opencode", "memory");
const DATA_FILE = join(DATA_DIR, "store.json");

function init() { mkdirSync(DATA_DIR, { recursive: true }); if (!existsSync(DATA_FILE)) writeFileSync(DATA_FILE, "[]", "utf-8"); }
function read() { try { return JSON.parse(readFileSync(DATA_FILE, "utf-8")); } catch { return []; } }
function write(d) { writeFileSync(DATA_FILE, JSON.stringify(d, null, 2), "utf-8"); }
function now() { return new Date().toISOString(); }

const TYPES = ["memory", "project", "person", "skill", "session", "config"];

function match(e, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  return e.name.toLowerCase().includes(q)
    || e.text.toLowerCase().includes(q)
    || e.category.toLowerCase().includes(q)
    || (e.tags || []).some(t => t.toLowerCase().includes(q));
}

function filterList(data, { type, scope, category }) {
  let f = data;
  if (type) f = f.filter(e => e.type === type);
  if (scope) f = f.filter(e => e.scope === scope);
  if (category) f = f.filter(e => e.category === category);
  return f;
}

const ENTITY_TYPES = tool.schema.enum(TYPES).optional().describe("Entity type filter");
const ENTITY_TYPE_REQ = tool.schema.enum(TYPES).describe("Entity type");

const plugin = async () => ({
  tool: {
    memory_store: tool({
      description: "Store a typed entity (memory/project/person/skill/session/config). Use type-specific tools for convenience.",
      args: {
        type: ENTITY_TYPE_REQ,
        name: tool.schema.string().optional().describe("Entity name/title"),
        text: tool.schema.string().describe("Main content/description"),
        category: tool.schema.string().optional().describe("Category tag"),
        scope: tool.schema.string().optional().describe("Scope (e.g. 'project:my-app', 'admin:global')"),
        importance: tool.schema.number().min(0).max(1).optional().describe("Importance 0-1"),
        tags: tool.schema.array(tool.schema.string()).optional().describe("Tags array"),
        data: tool.schema.object({}).optional().describe("Type-specific structured data as JSON object"),
      },
      async execute(args) {
        try {
          init(); const d = read();
          const e = {
            id: randomUUID(), type: args.type, name: args.name || "",
            text: args.text || "", category: args.category || "general",
            scope: args.scope || "admin:global", importance: args.importance ?? 0.5,
            tags: args.tags || [], data: args.data || {},
            source: "opencode", created_at: now(), updated_at: now(),
          };
          d.push(e); write(d);
          return `Stored ${args.type}: ${e.id}\nName: ${e.name || "(none)"}\nScope: ${e.scope}`;
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_recall: tool({
      description: "Search across all entity types by keyword. Use --type to filter.",
      args: {
        query: tool.schema.string().describe("Search text (matches name, content, tags)"),
        type: ENTITY_TYPES,
        scope: tool.schema.string().optional().describe("Filter by scope"),
        category: tool.schema.string().optional().describe("Filter by category"),
        limit: tool.schema.number().min(1).max(100).optional().describe("Max results, default 10"),
      },
      async execute(args) {
        try {
          init(); let data = read();
          if (args.type) data = data.filter(e => e.type === args.type);
          if (args.scope) data = data.filter(e => e.scope === args.scope);
          if (args.category) data = data.filter(e => e.category === args.category);
          data = data.filter(e => match(e, args.query));
          data.sort((a, b) => b.importance - a.importance || b.updated_at.localeCompare(a.updated_at));
          data = data.slice(0, args.limit || 10);
          if (!data.length) return "No results found.";
          const lines = [`Found ${data.length} result(s):\n`];
          data.forEach((r, i) => {
            const n = r.name ? ` [${r.name}]` : "";
            lines.push(`${i + 1}. (${r.type})${n} ${(r.text || "").substring(0, 120)}`);
            lines.push(`   Scope: ${r.scope} | Cat: ${r.category} | Imp: ${r.importance}`);
            if (r.tags && r.tags.length) lines.push(`   Tags: ${r.tags.join(", ")}`);
            lines.push("");
          });
          return lines.join("\n");
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_list: tool({
      description: "List entities with optional type/scope/category filter.",
      args: {
        type: ENTITY_TYPES,
        scope: tool.schema.string().optional().describe("Filter by scope"),
        category: tool.schema.string().optional().describe("Filter by category"),
        limit: tool.schema.number().min(1).max(100).optional().describe("Max results, default 50"),
      },
      async execute(args) {
        try {
          init(); let data = filterList(read(), args);
          data.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
          data = data.slice(0, args.limit || 50);
          if (!data.length) return `No ${args.type || "entities"} found.`;
          const label = args.type || "entities";
          const lines = [`Total: ${data.length} ${label}:\n`];
          data.forEach((r, i) => {
            const preview = (r.text || "").length > 80 ? (r.text || "").substring(0, 80) + "..." : (r.text || "");
            const n = r.name ? ` [${r.name}]` : "";
            lines.push(`${i + 1}. (${r.type})${n} ${preview}`);
            lines.push(`   ID: ${r.id} | Scope: ${r.scope} | Imp: ${r.importance}`);
          });
          return lines.join("\n");
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_get: tool({
      description: "Get a single entity by ID with full details.",
      args: { entityId: tool.schema.string().describe("Entity ID") },
      async execute({ entityId }) {
        try {
          init(); const e = read().find(x => x.id === entityId);
          if (!e) return "Entity not found.";
          return [
            `ID:   ${e.id}`,
            `Type: ${e.type}`,
            `Name: ${e.name || "(none)"}`,
            `Text: ${e.text}`,
            `Cat:  ${e.category}`,
            `Scope: ${e.scope}`,
            `Imp:  ${e.importance}`,
            `Tags: ${JSON.stringify(e.tags || [])}`,
            `Data: ${JSON.stringify(e.data || {}, null, 2)}`,
            `Src:  ${e.source}`,
            `Created: ${e.created_at}`,
            `Updated: ${e.updated_at}`,
          ].join("\n");
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_update: tool({
      description: "Update fields on an existing entity.",
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
      async execute(args) {
        try {
          init(); const d = read(); const idx = d.findIndex(x => x.id === args.entityId);
          if (idx === -1) return "Entity not found.";
          if (args.name !== undefined) d[idx].name = args.name;
          if (args.text !== undefined) d[idx].text = args.text;
          if (args.category !== undefined) d[idx].category = args.category;
          if (args.importance !== undefined) d[idx].importance = args.importance;
          if (args.scope !== undefined) d[idx].scope = args.scope;
          if (args.tags !== undefined) d[idx].tags = args.tags;
          if (args.data !== undefined) d[idx].data = args.data;
          d[idx].updated_at = now(); write(d);
          return "Updated.";
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_forget: tool({
      description: "Delete entities by ID, text query, scope, or type.",
      args: {
        entityId: tool.schema.string().optional().describe("Delete specific ID"),
        query: tool.schema.string().optional().describe("Delete matching content"),
        scope: tool.schema.string().optional().describe("Delete all in this scope"),
        type: ENTITY_TYPES,
      },
      async execute(args) {
        try {
          if (!args.entityId && !args.query && !args.scope && !args.type) return "Error: provide at least one filter (entityId, query, scope, or type)";
          init(); const before = read().length;
          const d = read().filter(e => {
            if (args.entityId && e.id === args.entityId) return false;
            if (args.query && match(e, args.query)) return false;
            if (args.scope && e.scope === args.scope) return false;
            if (args.type && e.type === args.type) return false;
            return true;
          });
          write(d); return `Deleted ${before - d.length}.`;
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_stats: tool({
      description: "Get memory store statistics by type/category/scope.",
      args: {},
      async execute() {
        try {
          init(); const data = read();
          const total = data.length;
          const byType = {}, byCat = {}, byScope = {};
          let oldest = null, newest = null;
          for (const e of data) {
            byType[e.type] = (byType[e.type] || 0) + 1;
            byCat[e.category] = (byCat[e.category] || 0) + 1;
            byScope[e.scope] = (byScope[e.scope] || 0) + 1;
            if (!oldest || e.created_at < oldest) oldest = e.created_at;
            if (!newest || e.updated_at > newest) newest = e.updated_at;
          }
          return [
            "Memory Statistics", "=".repeat(17),
            `Total: ${total}\n`,
            "By type:", ...Object.entries(byType).map(([k, v]) => `  ${k}: ${v}`),
            "\nBy category:", ...Object.entries(byCat).map(([k, v]) => `  ${k}: ${v}`),
            "\nBy scope:", ...Object.entries(byScope).map(([k, v]) => `  ${k}: ${v}`),
            `\nRange: ${oldest || "N/A"} to ${newest || "N/A"}`,
          ].join("\n");
        } catch (e) { return `Error: ${e.message || String(e)}`; }
      },
    }),

    memory_debug: tool({
      description: "Verify the plugin is loaded.",
      args: {},
      execute() { return "opencode-memory-store plugin is working!"; },
    }),
  },
});

export default plugin;
