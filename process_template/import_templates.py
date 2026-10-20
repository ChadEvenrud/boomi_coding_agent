#!/usr/bin/env python3
"""Import Boomi process templates from Timberlab/Templates folder."""

import html
import base64
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parent
WORKSPACE = TARGET_ROOT.parent
INVENTORY_DIR = TARGET_ROOT / "inventories"


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


class BoomiClient:
    def __init__(self, env: dict[str, str]) -> None:
        self.account_id = env["BOOMI_ACCOUNT_ID"]
        self.base_url = env["BOOMI_API_URL"].rstrip("/") + f"/api/rest/v1/{self.account_id}/"
        auth = base64.b64encode(
            f"BOOMI_TOKEN.{env['BOOMI_USERNAME']}:{env['BOOMI_API_TOKEN']}".encode()
        ).decode()
        self.headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "boomi-template-import/1.0",
        }
        self.xml_headers = {
            "Authorization": f"Basic {auth}",
            "Accept": "application/xml",
            "User-Agent": "boomi-template-import/1.0",
        }

    def post_json(self, endpoint: str, body: dict) -> dict:
        req = urllib.request.Request(
            self.base_url + endpoint,
            data=json.dumps(body).encode(),
            headers=self.headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)

    def get_xml(self, endpoint: str) -> str:
        req = urllib.request.Request(
            self.base_url + endpoint,
            headers=self.xml_headers,
            method="GET",
        )
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def query_all(self, entity: str, expression: dict) -> list[dict]:
        body = {"QueryFilter": {"expression": expression}}
        first = self.post_json(f"{entity}/query", body)
        results = list(first.get("result") or [])
        token = first.get("queryToken")
        while token:
            more = self.post_json(f"{entity}/queryMore", {"queryToken": token})
            results.extend(more.get("result") or [])
            token = more.get("queryToken")
        return results


GUID_PATTERN = re.compile(
    r'(?:mapId|calledProcess|connectionId|operationId|fromProfile|toProfile|'
    r'processId|profileId|docCache|subTypeComponentId|componentId)="([A-Za-z0-9+/=-]{10,})"'
)


def decode_name(name: str) -> str:
    return html.unescape(name)


def resolve_folder(client: BoomiClient, name: str) -> str:
    folders = client.query_all(
        "Folder",
        {"operator": "EQUALS", "property": "name", "argument": [name]},
    )
    if not folders:
        raise RuntimeError(f"No folder named '{name}' found.")

    if len(folders) == 1:
        return folders[0]["id"]

    # Prefer Timberlab path when multiple Templates folders exist.
    for folder in folders:
        path = (folder.get("folderFullPath") or folder.get("name") or "").lower()
        if "timberlab" in path and "templates" in path:
            return folder["id"]

    details = [
        f"{f.get('id')} :: {f.get('folderFullPath') or f.get('name')}"
        for f in folders
    ]
    raise RuntimeError(
        f"Multiple '{name}' folders found; specify folder id. Matches:\n"
        + "\n".join(details)
    )


def search_components(client: BoomiClient, folder_id: str, component_type: str | None = None) -> list[dict]:
    exprs = [
        {"operator": "EQUALS", "property": "currentVersion", "argument": ["true"]},
        {"operator": "EQUALS", "property": "deleted", "argument": ["false"]},
        {"operator": "EQUALS", "property": "folderId", "argument": [folder_id]},
    ]
    if component_type:
        exprs.append(
            {"operator": "EQUALS", "property": "type", "argument": [component_type]}
        )
    expression = exprs[0] if len(exprs) == 1 else {"operator": "AND", "nestedExpression": exprs}
    return client.query_all("ComponentMetadata", expression)


def safe_filename(name: str) -> str:
    name = re.sub(r"<([^>]+)>", r"_\1_", name)
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_. ")
    return cleaned or "unnamed_component"


def type_dir(component_type: str) -> str:
    return component_type.lower()


def extract_guids(xml: str, skip_ids: set[str] | None = None) -> set[str]:
    skip_ids = skip_ids or set()
    root_id_match = re.search(r'<(?:bns:)?component[^>]*componentId="([^"]+)"', xml)
    if root_id_match:
        skip_ids = skip_ids | {root_id_match.group(1)}
    found = set(GUID_PATTERN.findall(xml))
    return found - skip_ids


def pull_component(client: BoomiClient, component_id: str, pulled: dict[str, Path]) -> Path | None:
    if component_id in pulled:
        return pulled[component_id]

    try:
        xml = client.get_xml(f"Component/{component_id}")
    except urllib.error.HTTPError as exc:
        print(f"  WARN: failed to pull {component_id}: HTTP {exc.code}")
        return None

    name_match = re.search(r'name="([^"]*)"', xml)
    type_match = re.search(r'type="([^"]*)"', xml)
    name = decode_name(name_match.group(1) if name_match else "unknown")
    comp_type = type_match.group(1) if type_match else "unknown"

    out_dir = TARGET_ROOT / type_dir(comp_type)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_filename(name)}.xml"
    out_path.write_text(xml, encoding="utf-8")
    pulled[component_id] = out_path
    print(f"  Pulled {comp_type}: {name} -> {out_path.relative_to(WORKSPACE)}")
    return out_path


def main() -> None:
    env = load_env(WORKSPACE / ".env")
    client = BoomiClient(env)

    folder_id = resolve_folder(client, "Templates")
    print(f"Using Templates folder id: {folder_id}")

    components = search_components(client, folder_id, "process")
    print(f"Found {len(components)} process template(s)")

    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)
    inventory_path = INVENTORY_DIR / "templates_inventory.json"
    inventory_path.write_text(json.dumps(components, indent=2), encoding="utf-8")
    print(f"Inventory saved to {inventory_path.relative_to(WORKSPACE)}")

    pulled: dict[str, Path] = {}
    pending = [c.get("componentId") or c["id"] for c in components]

    # Pull root processes first.
    for component_id in pending:
        pull_component(client, component_id, pulled)

    # Pull direct GUID dependencies found in pulled XML (depth-limited).
    for depth in range(1, 4):
        new_ids: set[str] = set()
        for path in pulled.values():
            new_ids.update(extract_guids(path.read_text(encoding="utf-8")))
        new_ids -= set(pulled.keys())
        if not new_ids:
            break
        print(f"Pulling dependency depth {depth}: {len(new_ids)} component(s)")
        for component_id in sorted(new_ids):
            pull_component(client, component_id, pulled)

    summary = {
        "folder_id": folder_id,
        "process_count": len(components),
        "total_pulled": len(pulled),
        "components": [
            {
                "id": cid,
                "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
            }
            for cid, path in sorted(pulled.items(), key=lambda item: str(item[1]))
        ],
    }
    summary_path = INVENTORY_DIR / "import_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nImport complete: {len(components)} process(es), {len(pulled)} total component(s)")
    print(f"Summary: {summary_path.relative_to(WORKSPACE)}")


if __name__ == "__main__":
    main()
