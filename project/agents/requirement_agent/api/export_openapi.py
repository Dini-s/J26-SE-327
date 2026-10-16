"""Write the OpenAPI schema of the API to a file (default docs/c1_openapi.json next to the project folder).

    python -m agents.requirement_agent.api.export_openapi [path]

Uses a temporary workspace, so it does not touch outputs/c1_workspace/.
"""
import json
import sys
import tempfile
from pathlib import Path

from .app import create_app
from .settings import PROJECT_ROOT


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    target = Path(argv[0]) if argv else PROJECT_ROOT.parent / "docs" / "c1_openapi.json"
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(workspace=tmp, backend_name="mock")
        schema = app.openapi()
        app.state.manager.stop()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {target} ({len(schema['paths'])} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
