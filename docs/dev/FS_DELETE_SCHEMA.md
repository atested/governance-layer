# FS_DELETE Intent Schema

This document defines the Phase 2D FS_DELETE intent payload and normalized args
recorded in decision records.

## Intent schema

- `capability_class`: string, required, must equal `"FS_DELETE"`
- `path`: string, required
- `recursive`: boolean, optional, defaults to `false`

Example:

```json
{
  "capability_class": "FS_DELETE",
  "path": "docs/tmp",
  "recursive": false
}
```

## Normalized args (decision record)

- `canonical_path`: string
- `recursive_requested`: boolean

Example:

```json
{
  "normalized_args": {
    "canonical_path": "/repo/docs/tmp",
    "recursive_requested": false
  }
}
```

## Consistency note

FS_DELETE mirrors the FS_MKDIR single-path pattern, with one boolean flag
(`recursive`) carried into normalized args as `recursive_requested`.

## Related reason codes

- `RC-FS-PATH-DISALLOWED`
- `RC-FS-PATH-TRAVERSAL`
- `RC-FS-HIDDEN-PATH`
- `RC-FS-RECURSIVE-DISALLOWED`
