"""Export OpenAPI 3.1 specification and TypeScript contract interface.

Single source of truth pipeline: FastAPI (Pydantic v2) -> OpenAPI 3.1 -> TypeScript.
Per ADR-0012, no hand-written TypeScript domain definitions are permitted.
"""

import json
from pathlib import Path
import sys

# Ensure apps/api and packages/domain are on path
REPO_ROOT = Path(__file__).resolve().parent.parent
API_SRC = REPO_ROOT / "apps" / "api" / "src"
DOMAIN_SRC = REPO_ROOT / "packages" / "domain" / "src"

sys.path.insert(0, str(API_SRC))
sys.path.insert(0, str(DOMAIN_SRC))

from croviq_api.main import app  # noqa: E402


def export_openapi_json(output_path: Path) -> dict:
    """Extract and export OpenAPI 3.1 JSON from FastAPI."""
    openapi_schema = app.openapi()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    return openapi_schema


def generate_typescript_contracts(openapi_schema: dict, output_path: Path) -> None:
    """Generate TypeScript contracts file from OpenAPI specification."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = """/**
 * Auto-generated OpenAPI TypeScript contract interfaces for Croviq.
 * Generated from FastAPI OpenAPI 3.1 specification.
 *
 * DO NOT EDIT MANUALLY (ADR-0012: Python Pydantic v2 is the single source of truth).
 *
 * NOTE: Canonical domain models (User, Workspace, BrandKit) from packages/domain
 * will appear automatically in these contracts when real business endpoints are
 * attached in Milestone 2A (#15: /auth/me and #16: /workspaces).
 */

export interface paths {
"""
    # Generate paths
    paths = openapi_schema.get("paths", {})
    path_entries = []
    for path_key, methods in paths.items():
        method_entries = []
        for method, op in methods.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue
            responses = op.get("responses", {})
            resp_types = []
            for status_code, resp_obj in responses.items():
                content = resp_obj.get("content", {})
                schema = content.get("application/json", {}).get("schema", {})
                ref = schema.get("$ref")
                if ref:
                    schema_name = ref.split("/")[-1]
                    resp_types.append(f"{status_code}: components['schemas']['{schema_name}'];")
                else:
                    resp_types.append(f"{status_code}: unknown;")
            responses_str = " ".join(resp_types)
            method_entries.append(f'      {method.lower()}: {{\n        responses: {{\n          {responses_str}\n        }};\n      }};')
        methods_str = "\n".join(method_entries)
        path_entries.append(f'  "{path_key}": {{\n{methods_str}\n  }};')

    paths_body = "\n".join(path_entries)
    if not paths_body:
        paths_body = "  // Endpoints will populate here as routes are registered.\n"

    # Generate schemas
    components_header = "\n}\n\nexport interface components {\n  schemas: {\n"
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    schema_entries = []

    def json_schema_to_ts(prop_schema: dict) -> str:
        if "$ref" in prop_schema:
            ref_name = prop_schema["$ref"].split("/")[-1]
            return f"components['schemas']['{ref_name}']"
        if "const" in prop_schema:
            return json.dumps(prop_schema["const"])
        if "enum" in prop_schema:
            return " | ".join(json.dumps(val) for val in prop_schema["enum"])
        if "oneOf" in prop_schema:
            types = [json_schema_to_ts(s) for s in prop_schema["oneOf"]]
            return " | ".join(types)
        if "anyOf" in prop_schema:
            types = [json_schema_to_ts(s) for s in prop_schema["anyOf"]]
            return " | ".join(types)
        prop_type = prop_schema.get("type")
        if prop_type == "string":
            return "string"
        if prop_type == "integer" or prop_type == "number":
            return "number"
        if prop_type == "boolean":
            return "boolean"
        if prop_type == "null":
            return "null"
        if prop_type == "array":
            items = prop_schema.get("items", {})
            return f"{json_schema_to_ts(items)}[]"
        if prop_type == "object":
            return "Record<string, unknown>"
        return "unknown"
    for schema_name, schema_data in schemas.items():
        if "enum" in schema_data:
            enum_vals = " | ".join(json.dumps(val) for val in schema_data["enum"])
            schema_entries.append(f"    {schema_name}: {enum_vals};")
            continue
        properties = schema_data.get("properties", {})
        required = set(schema_data.get("required", []))
        prop_lines = []
        for prop_name, prop_val in properties.items():
            is_req = prop_name in required
            opt_marker = "" if is_req else "?"
            ts_type = json_schema_to_ts(prop_val)
            doc = prop_val.get("description")
            doc_str = f"      /** {doc} */\n" if doc else ""
            prop_lines.append(f"{doc_str}      {prop_name}{opt_marker}: {ts_type};")
        body = "\n".join(prop_lines)
        schema_entries.append(f"    {schema_name}: {{\n{body}\n    }};")
    schemas_body = "\n".join(schema_entries)
    components_footer = "\n  };\n}\n"

    content = header + paths_body + components_header + schemas_body + components_footer
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    openapi_json_path = REPO_ROOT / "openapi.json"
    ts_output_path = REPO_ROOT / "apps" / "web" / "src" / "api" / "generated.ts"

    schema = export_openapi_json(openapi_json_path)
    generate_typescript_contracts(schema, ts_output_path)
    print(f"Exported OpenAPI 3.1 to: {openapi_json_path}")
    print(f"Generated TypeScript contracts to: {ts_output_path}")


if __name__ == "__main__":
    main()
