#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# OmniTradePro - headless Qt ABI shims (CI / Linux container only)
#
# The PySide6 wheels link against libGL / libEGL / libxkbcommon / libdbus, which
# minimal Linux containers do not ship. On a real Windows desktop (the target
# platform) none of this is needed. This script builds minimal stub libraries so
# the Qt event loop can run with QT_QPA_PLATFORM=offscreen, which is what the
# audit harness (audit_production_certification.py) uses.
#
# Usage:
#   bash tools/build_headless_qt_shims.sh
#   export LD_LIBRARY_PATH="$PWD/.shim:$LD_LIBRARY_PATH"
#   export QT_QPA_PLATFORM=offscreen
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/.shim"
mkdir -p "$OUT"

PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY=python3

"$PY" - "$OUT" <<'PYEOF'
import re, subprocess, sys, os, glob, json
from pathlib import Path

out = Path(sys.argv[1])
pyside = Path(subprocess.run([sys.executable, "-c", "import PySide6,os;print(os.path.dirname(PySide6.__file__))"],
                             capture_output=True, text=True).stdout.strip())
qtdir = pyside / "Qt" / "lib"
targets = [qtdir / n for n in (
    "libQt6Core.so.6", "libQt6Gui.so.6", "libQt6Widgets.so.6", "libQt6DBus.so.6",
    "libQt6Network.so.6", "libQt6Svg.so.6", "libQt6PrintSupport.so.6",
    # pyqtgraph imports QtOpenGL at module load, so its GL entry points must
    # be covered too even when the chart itself only paints with QPainter.
    "libQt6OpenGL.so.6", "libQt6OpenGLWidgets.so.6",
)]
# The platform plugin and the Shiboken extension modules are loaded at runtime
# too; their GL/EGL references must be visible for the loader to resolve them.
targets += [p for p in (qtdir.parent / "plugins" / "platforms").glob("*offscreen*.so")]
targets += list(pyside.glob("Qt*.abi3.so"))
targets = [t for t in targets if t.exists()]

def undefined(path):
    text = subprocess.run(["objdump", "-T", str(path)], capture_output=True, text=True).stdout
    syms = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or "*UND*" not in parts:
            continue
        m = re.search(r"\(([A-Za-z0-9_.]+)\)\s+(\S+)$", line)
        syms[m.group(2) if m else parts[-1]] = m.group(1) if m else None
    return syms

needed = {}
for t in targets:
    needed.update(undefined(t))

def build(name, pattern, filename, version_node=None):
    """Emits a stub .so exporting every still-unresolved symbol matching `pattern`.

    A version node is required where the Qt libraries reference versioned symbols
    (libxkbcommon's V_0.5.0, libdbus's LIBDBUS_1_3); without it glibc aborts the
    process with an ld.so consistency assertion instead of a clean error.
    """
    syms = sorted(s for s in needed if re.match(pattern, s))
    if not syms:
        return
    c = out / f"{name}.c"
    c.write_text("#include <stdint.h>\n" + "".join(f"void* {s}(void){{return 0;}}\n" for s in syms))
    cmd = ["gcc", "-shared", "-fPIC", "-o", str(out / filename), str(c)]
    if version_node:
        # Version scripts take an explicit symbol list, not a regex.
        vf = out / f"{name}.map"
        vf.write_text(f"{version_node} {{ global: {'; '.join(syms)}; local: *; }};\n")
        cmd[1:1] = [f"-Wl,--version-script={vf}"]
    subprocess.run(cmd, check=True)
    print(f"built {filename} ({len(syms)} symbols)")

build("gl", r"(gl|glX|__gl)", "libGL.so.1")
build("egl", r"egl", "libEGL.so.1")
build("xkb", r"xkb_", "libxkbcommon.so.0", version_node="V_0.5.0")
build("dbus", r"dbus_", "libdbus-1.so.3", version_node="LIBDBUS_1_3")
PYEOF

echo "Headless Qt shims written to $OUT"
