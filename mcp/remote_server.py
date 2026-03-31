#!/usr/bin/env python3
import json
import sys

import server as govmcp_server


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-config":
        print(json.dumps(govmcp_server.remote_runtime_contract(), sort_keys=True, separators=(",", ":")))
        return 0
    govmcp_server.run_remote_streamable_http()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
