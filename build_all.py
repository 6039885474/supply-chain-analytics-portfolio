"""Rebuild both synthetic projects and a portable, static portfolio website.

Python 3.10+, standard library only. Run from any working directory.
"""
from pathlib import Path
import html
import json
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
PROJECTS = ("inventory_fulfillment", "delivery_returns")


def source_files(folder):
    for path in sorted(folder.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and ".git" not in path.parts and path.suffix not in {".pyc", ".sqlite", ".db"}:
            yield path


def archive_project(folder, target):
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files(folder):
            info = zipfile.ZipInfo(str(Path(folder.name) / path.relative_to(folder)).replace("\\", "/"), (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def preview_svg(title, subtitle, rows, name_key, value_key, color):
    elements = []
    for i, row in enumerate(rows):
        value = float(row[value_key])
        y = 119 + i * 54
        label = html.escape(row[name_key])
        elements.append(f'<text x="26" y="{y}" fill="#516b77" font-size="12">{label}</text><rect x="202" y="{y-12}" width="320" height="16" rx="4" fill="#e6eeeb"/><rect x="202" y="{y-12}" width="{3.2*value:.2f}" height="16" rx="4" fill="{color}"/><text x="580" y="{y}" text-anchor="end" fill="#18313c" font-size="13">{value:.2f}%</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="620" height="295" viewBox="0 0 620 295" role="img" aria-label="{html.escape(title)}"><rect width="620" height="295" rx="12" fill="#f5f8f6"/><g font-family="Arial,sans-serif"><text x="26" y="38" font-size="21" font-weight="700" fill="#18313c">{html.escape(title)}</text><text x="26" y="62" font-size="11" fill="#627783">{html.escape(subtitle)}</text>{"".join(elements)}<text x="26" y="277" font-size="10" fill="#627783">Synthetic data · January–February 2026 · full-period observations</text></g></svg>'


def main():
    docs = ROOT / "docs"
    assets = docs / "assets"
    files = docs / "files"
    previews = docs / "previews"
    for path in (docs, assets, files, previews):
        path.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for name in PROJECTS:
        project = ROOT / "projects" / name
        result = subprocess.run([sys.executable, str(project / "build.py")], cwd=project, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"{name} failed:\n{result.stdout}\n{result.stderr}")
        data = json.loads((project / "dashboard_data.json").read_text())
        assert data["summary"] and data["definitions"], f"Missing dashboard contract: {name}"
        datasets[name] = data
        short, global_name = ("inventory", "INVENTORY_DATA") if name == PROJECTS[0] else ("delivery", "DELIVERY_DATA")
        # Script assignment enables opening docs/index.html without a web server.
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        (assets / f"{short}-data.js").write_text(f"window.{global_name} = {payload};\n", encoding="utf-8")
        archive_project(project, files / f"{name}.zip")
    for name, target in (("index.html", docs / "index.html"), ("style.css", assets / "style.css"), ("app.js", assets / "app.js")):
        shutil.copy2(ROOT / "site_source" / name, target)
    (docs / ".nojekyll").write_text("")
    inv, delivery = (datasets[k] for k in PROJECTS)
    (previews / "inventory.svg").write_text(preview_svg("Inventory & fulfillment", "On-time dispatch among due, noncancelled orders", inv["warehouses"], "warehouse_name", "on_time_dispatch_pct", "#168477"))
    (previews / "delivery.svg").write_text(preview_svg("Delivery & returns", "First-attempt success among observed eligible first attempts", delivery["hubs"], "hub_name", "first_attempt_success_rate_pct", "#c7864b"))
    print(json.dumps({"status": "built", "website": "docs/index.html", "inventory_orders": inv["summary"]["orders_created"], "delivery_shipments": delivery["summary"]["shipments"], "external_python_dependencies": 0}, indent=2))


if __name__ == "__main__":
    main()
