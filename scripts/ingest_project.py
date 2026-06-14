"""Ingest all LAN Box project files into memory store."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from opencode_memory_store.store import MemoryStore, get_db_path

PROJECT = Path(r"E:\SCRIPTS\Utilities\I_will_name_you_later")

store = MemoryStore(get_db_path())

def store_entity(type_, name, text, category, tags=None, data=None):
    existing = store.list_entities(type=type_)
    for e in existing:
        if e["name"] == name:
            store.update(e["id"], text=text, tags=tags or [], data=data or {})
            print(f"  Updated {type_}: {name}")
            return
    store.store(type=type_, name=name, text=text, category=category,
                tags=tags or [], data=data or {})
    print(f"  Stored {type_}: {name}")

# ── Project itself ──
readme = (PROJECT / "README.md").read_text(encoding="utf-8")
project_text = readme
store_entity("project", "LAN Box",
    "Cross-platform network toolkit: SSH terminal, Wake-on-LAN, ARP scanner, device discovery. "
    "Built with Flutter for Windows & Android.",
    "app", ["flutter", "dart", "network", "ssh", "wol", "lan", "arp", "windows", "android"],
    {"readme": readme, "repo": "git@github.com:coff33ninja/lan-box.git", "author": "coff33ninja"})

# ── Architecture ──
arch = (PROJECT / "docs" / "architecture.md").read_text(encoding="utf-8")
store_entity("config", "Architecture",
    "4-layer design: UI → State (Riverpod) → Service → PlatformAdapter. "
    "Pure Dart SSH via dartssh2, drift SQLite for persistence, GoRouter for navigation.",
    "architecture", ["layered", "riverpod", "drift", "go_router", "platform-adapter"],
    {"content": arch})

# ── Implementation Plan ──
impl = (PROJECT / "docs" / "implementation-plan.md").read_text(encoding="utf-8")
store_entity("memory", "Implementation Plan",
    "6 phases over 19-25 days: Core+DB, Scanner, WOL, SSH Terminal, Responsive UI, Polish.",
    "planning", ["phases", "milestones", "roadmap"],
    {"content": impl})

# ── Network Services ──
net = (PROJECT / "docs" / "network-services.md").read_text(encoding="utf-8")
store_entity("skill", "Network - WOL, ARP, Ping, Port Scan",
    "ARP table parsing, ICMP ping sweep, Wake-on-LAN magic packets via RawDatagramSocket, "
    "mDNS discovery with multicast_dns, TCP port scanning. Pure Dart except ARP.",
    "networking", ["wol", "arp", "ping", "mdns", "port-scan"],
    {"content": net})

# ── SSH Terminal ──
ssh = (PROJECT / "docs" / "ssh-terminal.md").read_text(encoding="utf-8")
store_entity("skill", "SSH Terminal - dartssh2 + VT100",
    "Multi-tab SSH with VT100/xterm emulation via dartssh2. Password/key/agent auth, "
    "PTY allocation, terminal rendering with TextPainter, persistent sessions.",
    "networking", ["ssh", "terminal", "vt100", "dartssh2"],
    {"content": ssh})

# ── State Management ──
state = (PROJECT / "docs" / "state-management.md").read_text(encoding="utf-8")
store_entity("config", "State Management - Riverpod",
    "Riverpod 2.x with freezed models. Cross-screen sharing via deviceListProvider. "
    "keepAlive for SSH sessions. StreamProvider for connectivity.",
    "architecture", ["riverpod", "state", "freezed", "providers"],
    {"content": state})

# ── Responsive UI ──
resp = (PROJECT / "docs" / "responsive-ui.md").read_text(encoding="utf-8")
store_entity("config", "Responsive UI - MainShell / TabletShell",
    "Two shells selected by width breakpoint (<600dp phone, 600-840 wide, >=840 tablet). "
    "MainShell with BottomNavigationBar, TabletShell with NavigationRail + detail pane.",
    "ui", ["responsive", "shells", "navigation", "adaptive"],
    {"content": resp})

# ── Platform Adaptation ──
plat = (PROJECT / "docs" / "platform-adaptation.md").read_text(encoding="utf-8")
store_entity("config", "Platform Adaptation - WindowsAdapter/AndroidAdapter",
    "Abstract PlatformAdapter interface in core/. Windows: arp -a, ping -n. "
    "Android: /proc/net/arp, ping -c. Selected via ProviderScope at app startup.",
    "architecture", ["windows", "android", "platform", "adapter"],
    {"content": plat})

# ── Routing ──
route = (PROJECT / "docs" / "routing.md").read_text(encoding="utf-8")
store_entity("config", "Routing - GoRouter StatefulShellRoute",
    "GoRouter 14.x with StatefulShellRoute for tab persistence. "
    "Shell selection by width, deep linking to terminal sessions and device details.",
    "ui", ["go_router", "routing", "navigation", "deep-linking"],
    {"content": route})

# ── Code structure overview ──
code_structure = """lib/
├── main.dart / app.dart          - Entry point + ProviderScope
├── core/
│   ├── network/                   - WOL, ARP, ping, port scan, mDNS
│   ├── ssh/                       - SSH client, terminal emulator
│   ├── platform/adapter.dart      - Abstract PlatformAdapter
│   ├── storage/                   - drift DB, credential store
│   └── utils/                     - MAC parsing
├── state/                         - Riverpod providers
├── ui/shells/                     - MainShell (phone), TabletShell (tablet)
├── ui/screens/                    - Dashboard, Scanner, Terminal, WOL
├── ui/shared/                     - Theme, responsive layout
├── platform/                      - WindowsAdapter, AndroidAdapter
└── router/                        - GoRouter config"""
store_entity("config", "Code Structure",
    code_structure,
    "architecture", ["project-structure", "layers", "code-organization"],
    {})

# ── Key files by path ──
files_info = {
    "main.dart": "Entry point - WidgetsFlutterBinding + ProviderScope + LanBoxApp",
    "app.dart": "App widget - platformAdapterProvider, MaterialApp.router with GoRouter",
    "core/storage/database.dart": "drift SQLite - DeviceRecords, WolHistoryRecords tables, AppDatabase",
    "core/storage/credential_store.dart": "JSON file-based credential storage for SSH passwords",
    "core/network/wol.dart": "WakeOnLan - magic packet builder, UDP broadcast on port 9",
    "core/network/subnet_utils.dart": "Subnet CIDR math, IP range generation",
    "core/platform/adapter.dart": "PlatformAdapter abstract class + ArpEntry + NetworkInterfaceInfo",
    "core/utils/mac_utils.dart": "MacAddress parser/formatter + OUI vendor lookup table",
    "platform/windows_adapter.dart": "WindowsAdapter - arp -a parsing, ping -n",
    "platform/android_adapter.dart": "AndroidAdapter - /proc/net/arp parsing, ping -c",
    "state/device_list/device.dart": "Device model with DeviceStatus enum, copyWith, JSON serialization",
    "state/device_list/device_notifier.dart": "DeviceListNotifier - StateNotifier with DB CRUD + scan merge",
    "state/device_list/device_providers.dart": "Riverpod providers - database, deviceList, byId, counts",
    "router/app_router.dart": "GoRouter with StatefulShellRoute, 4 tabs + settings/about",
    "router/route_names.dart": "RoutePaths constants - /dashboard, /scanner, /terminal, /wol",
    "ui/shared/theme/app_theme.dart": "AppTheme - light/dark/terminal theme, JetBrainsMono font",
    "ui/shells/main_shell.dart": "MainShell phone layout - Scaffold + NavigationBar with 4 tabs",
    "ui/shells/tablet_shell.dart": "TabletShell - Row with NavigationRail + VerticalDivider + child",
    "ui/screens/dashboard/dashboard_screen.dart": "Dashboard with stat cards (total/online/offline) + recent devices list",
    "ui/screens/scanner/scanner_screen.dart": "Scanner placeholder - ARP scanning, ping sweep, mDNS (Phase 2)",
    "ui/screens/terminal/terminal_screen.dart": "Terminal placeholder - multi-tab SSH (Phase 4)",
    "ui/screens/wol/wol_screen.dart": "WOL placeholder - magic packets + schedules (Phase 3)",
    "ui/screens/settings_screen.dart": "Settings placeholder",
    "ui/screens/about_screen.dart": "About screen with version info",
    "ui/screens/not_found_screen.dart": "404 error screen",
}

for path, desc in files_info.items():
    full_path = PROJECT / "lib" / path
    code = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
    name = f"lib/{path}"
    tags = ["dart", "flutter"] + path.replace("\\", "/").split("/")
    store_entity("memory", name, desc, "code", tags, {"path": f"lib/{path}", "code": code})

# ── Scripts ──
for script in sorted((PROJECT / "scripts").glob("*.ps1")):
    name = script.stem
    content = script.read_text(encoding="utf-8")
    desc_lines = [l for l in content.split("\n") if l.startswith("#")]
    desc = desc_lines[0].lstrip("# ").strip() if desc_lines else f"PowerShell script: {name}"
    tags = ["powershell", "script"] + name.split("-")
    store_entity("skill", f"Script - {name}", desc, "tooling", tags, {"path": f"scripts/{script.name}", "content": content})

print("\nDone!")
