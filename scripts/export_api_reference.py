#!/usr/bin/env python3
"""Write docs/api_reference.md from the live OpenAPI schema. Run after changing routes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from app.main import app
    spec = app.openapi()
    out = ["# API reference", "", f"Generated from the OpenAPI schema of CorridorComply {spec['info'].get('version', '')}. "
           "Interactive docs at `/docs`; raw schema at `/openapi.json`.", "",
           "All `/api/v1/*` routes require `X-API-Key` when keys are configured. Every request may carry `X-Request-ID`; "
           "the response echoes it and every audit event and stored record cites it.", ""]
    by_tag = {}
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            for tag in op.get("tags", ["Other"]):
                by_tag.setdefault(tag, []).append((method.upper(), path, op))
    for tag, ops in by_tag.items():
        out += [f"## {tag}", ""]
        for method, path, op in ops:
            out += [f"### `{method} {path}`", ""]
            if op.get("summary") or op.get("description"):
                out += [(op.get("description") or op.get("summary")).strip(), ""]
            params = op.get("parameters", [])
            if params:
                out += ["Parameters:", ""]
                for p in params:
                    sch = p.get("schema", {})
                    out.append(f"- `{p['name']}` ({p['in']}{', required' if p.get('required') else ''}): {p.get('description') or sch.get('type', '')}")
                out.append("")
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            if body.get("$ref"):
                out += [f"Request body: `{body['$ref'].split('/')[-1]}`", ""]
            resp = op.get("responses", {}).get("200", {}).get("content", {}).get("application/json", {}).get("schema", {})
            if resp.get("$ref"):
                out += [f"Response: `{resp['$ref'].split('/')[-1]}`", ""]
    out += ["## Schemas", ""]
    for name, schema in spec.get("components", {}).get("schemas", {}).items():
        if name.startswith("HTTPValidationError") or name == "ValidationError":
            continue
        out += [f"### `{name}`", ""]
        props = schema.get("properties", {})
        req = set(schema.get("required", []))
        for pname, p in props.items():
            typ = p.get("type") or ("/".join(x.get("type", "") for x in p.get("anyOf", [])) if p.get("anyOf") else "") or ("ref" if "$ref" in p else "")
            desc = p.get("description", "")
            out.append(f"- `{pname}`{' (required)' if pname in req else ''}: {typ}{' — ' + desc if desc else ''}")
        out.append("")
    Path("docs/api_reference.md").write_text("\n".join(out))
    print(f"wrote docs/api_reference.md ({len(out)} lines, {len(spec['paths'])} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
