import { tool } from "@opencode-ai/plugin/tool";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const DATA_DIR = join(homedir(), ".opencode", "memory");
const DATA_FILE = join(DATA_DIR, "store.json");

function initStore() {
  mkdirSync(DATA_DIR, { recursive: true });
  if (!existsSync(DATA_FILE)) writeFileSync(DATA_FILE, "[]", "utf-8");
}

function readStore() {
  try {
    return JSON.parse(readFileSync(DATA_FILE, "utf-8"));
  } catch {
    return [];
  }
}

function writeStore(data) {
  writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), "utf-8");
}

function now() {
  return new Date().toISOString();
}

function matches(mem, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  return mem.text.toLowerCase().includes(q)
    || mem.category.toLowerCase().includes(q)
    || mem.scope.toLowerCase().includes(q);
}

const plugin = async () => ({
  tool: {
    memory_store: tool({
      description: "Store a new memory in the agent's long-term memory.",
      args: {
        text: tool.schema.string().describe("The memory text"),
        category: tool.schema.enum(["preference", "fact", "decision", "entity", "other"]).optional().describe("Category"),
        scope: tool.schema.string().optional().describe("Scope (e.g. 'admin:global')"),
        importance: tool.schema.number().min(0).max(1).optional().describe("Importance 0-1"),
      },
      async execute(args) {
        try {
          initStore();
          const data = readStore();
          const mem = {
            id: randomUUID(),
            text: args.text,
            category: args.category || "fact",
            scope: args.scope || "admin:global",
            importance: args.importance ?? 0.5,
            created_at: now(),
            updated_at: now(),
          };
          data.push(mem);
          writeStore(data);
          return `Memory stored successfully!\nID: ${mem.id}\nCategory: ${mem.category}\nScope: ${mem.scope}`;
        } catch (e) {
          return `Error storing memory: ${e.message || String(e)}`;
        }
      },
    }),

    memory_recall: tool({
      description: "Search memories by keyword text.",
      args: {
        query: tool.schema.string().describe("Search query text"),
        scope: tool.schema.string().optional().describe("Filter by scope"),
        category: tool.schema.enum(["preference", "fact", "decision", "entity", "other"]).optional().describe("Filter by category"),
        limit: tool.schema.number().min(1).max(100).optional().describe("Max results"),
      },
      async execute(args) {
        try {
          initStore();
          const data = readStore();
          let results = data.filter(m => {
            if (args.category && m.category !== args.category) return false;
            if (args.scope && m.scope !== args.scope) return false;
            return matches(m, args.query);
          });
          results.sort((a, b) => b.importance - a.importance || b.updated_at.localeCompare(a.updated_at));
          results = results.slice(0, args.limit || 10);
          if (!results.length) return "No memories found.";
          const lines = [`Found ${results.length} memory(ies):\n`];
          results.forEach((r, i) => {
            lines.push(`${i + 1}. [${r.category}] ${r.text.substring(0, 120)}`);
            lines.push(`   Score: 100% | Scope: ${r.scope} | Importance: ${r.importance}`);
            lines.push("");
          });
          return lines.join("\n");
        } catch (e) {
          return `Error recalling memories: ${e.message || String(e)}`;
        }
      },
    }),

    memory_forget: tool({
      description: "Delete memories by ID, query, or scope.",
      args: {
        memoryId: tool.schema.string().optional().describe("Specific memory ID"),
        query: tool.schema.string().optional().describe("Delete memories matching text query"),
        scope: tool.schema.string().optional().describe("Delete all memories in this scope"),
      },
      async execute(args) {
        try {
          initStore();
          let data = readStore();
          const before = data.length;
          data = data.filter(m => {
            if (args.memoryId && m.id === args.memoryId) return false;
            if (args.query && matches(m, args.query)) return false;
            if (args.scope && m.scope === args.scope) return false;
            return true;
          });
          if (!args.memoryId && !args.query && !args.scope) {
            return "Error: provide memoryId, query, or scope";
          }
          writeStore(data);
          return `Deleted ${before - data.length} memory(ies)`;
        } catch (e) {
          return `Error forgetting memories: ${e.message || String(e)}`;
        }
      },
    }),

    memory_list: tool({
      description: "List stored memories. Filter by scope or category.",
      args: {
        scope: tool.schema.string().optional().describe("Filter by scope"),
        category: tool.schema.enum(["preference", "fact", "decision", "entity", "other"]).optional().describe("Filter by category"),
        limit: tool.schema.number().min(1).max(100).optional().describe("Max results"),
      },
      async execute(args) {
        try {
          initStore();
          let data = readStore();
          if (args.scope) data = data.filter(m => m.scope === args.scope);
          if (args.category) data = data.filter(m => m.category === args.category);
          data.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
          data = data.slice(0, args.limit || 50);
          if (!data.length) return "No memories found.";
          const lines = [`Total: ${data.length} memories:\n`];
          data.forEach((m, i) => {
            const preview = m.text.length > 80 ? m.text.substring(0, 80) + "..." : m.text;
            lines.push(`${i + 1}. [${m.category}] ${preview}`);
            lines.push(`   ID: ${m.id} | Scope: ${m.scope} | Importance: ${m.importance}`);
          });
          return lines.join("\n");
        } catch (e) {
          return `Error listing memories: ${e.message || String(e)}`;
        }
      },
    }),

    memory_update: tool({
      description: "Update an existing memory.",
      args: {
        memoryId: tool.schema.string().describe("The memory ID to update"),
        text: tool.schema.string().optional().describe("New text"),
        category: tool.schema.enum(["preference", "fact", "decision", "entity", "other"]).optional().describe("New category"),
        importance: tool.schema.number().min(0).max(1).optional().describe("New importance"),
        scope: tool.schema.string().optional().describe("New scope"),
      },
      async execute(args) {
        try {
          initStore();
          const data = readStore();
          const idx = data.findIndex(m => m.id === args.memoryId);
          if (idx === -1) return "Memory not found.";
          if (args.text !== undefined) data[idx].text = args.text;
          if (args.category !== undefined) data[idx].category = args.category;
          if (args.importance !== undefined) data[idx].importance = args.importance;
          if (args.scope !== undefined) data[idx].scope = args.scope;
          data[idx].updated_at = now();
          writeStore(data);
          return "Memory updated successfully!";
        } catch (e) {
          return `Error updating memory: ${e.message || String(e)}`;
        }
      },
    }),

    memory_stats: tool({
      description: "Get memory store statistics.",
      args: {},
      async execute() {
        try {
          initStore();
          const data = readStore();
          const total = data.length;
          const byCategory = {};
          const byScope = {};
          let oldest = null, newest = null;
          for (const m of data) {
            byCategory[m.category] = (byCategory[m.category] || 0) + 1;
            byScope[m.scope] = (byScope[m.scope] || 0) + 1;
            if (!oldest || m.created_at < oldest) oldest = m.created_at;
            if (!newest || m.updated_at > newest) newest = m.updated_at;
          }
          return [
            "Memory Statistics",
            "=================",
            `Total memories: ${total}\n`,
            "By category:",
            ...Object.entries(byCategory).map(([k, v]) => `  ${k}: ${v}`),
            "\nBy scope:",
            ...Object.entries(byScope).map(([k, v]) => `  ${k}: ${v}`),
            `\nTime range: ${oldest || "N/A"} to ${newest || "N/A"}`,
          ].join("\n");
        } catch (e) {
          return `Error getting stats: ${e.message || String(e)}`;
        }
      },
    }),

    memory_debug: tool({
      description: "Debug tool to verify the plugin is loaded.",
      args: {},
      execute() {
        return "opencode-memory-store plugin is working!";
      },
    }),
  },
});

export default plugin;
