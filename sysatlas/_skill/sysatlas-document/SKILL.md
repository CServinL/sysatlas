---
name: sysatlas-document
description: Use to document a project's architecture with sysatlas. Fills the "Documentation gaps" of the architecture atlas — writes missing docstrings, records what each component is for and which architectural patterns it follows in docs/reflection/intent.json, then regenerates docs/reflection/atlas.md. Use after structural changes, or when the atlas lists gaps.
user-invocable: true
---

# sysatlas-document — close the documentation gaps in the atlas

The atlas maps what code can show: modules, imports, entry points, external
systems, data models. It cannot say what a component is **for**, or which
design patterns it follows. You write that part, from reading the source.

## Steps

1. **Regenerate and read the atlas.** Pass the intent file if it exists.

   ```python
   import sysatlas
   r = sysatlas.reflect("path/to/source/root")
   print(r.to_atlas(title="…", intent="docs/reflection/intent.json"))
   ```

   (Omit `intent=` on the first run.) Read the last section, "Documentation
   gaps". Each component there carries a fingerprint in square brackets.

2. **Docstrings.** For each module under "Modules without a docstring", read
   it and add a module docstring. The first line is one sentence: what the
   module is responsible for. For each public symbol under "Public symbols
   without a docstring", add a short docstring that states its purpose and any
   contract that is not obvious from the signature.

3. **Component purposes.** For each component under "no intent recorded" or
   "intent is stale", read its member modules, then add an entry to
   `docs/reflection/intent.json`. Write one or two sentences: what the
   component is responsible for, and what it must not do. Copy its fingerprint
   exactly. Leave entries that are still current alone. Delete entries listed
   under "no longer exist".

4. **Patterns.** Add a pattern to `patterns` only when the code shows it. Name
   it, say in one sentence how it appears here, and list the components that
   take part. Examples: layered, pipeline, plugin registry, ports and adapters,
   repository, fluent builder, state machine, facade, publish and subscribe.
   If you are not sure, leave it out.

5. **Summary.** Set `summary` to one short paragraph: what the system is for
   and who uses it.

6. **Verify.** Regenerate with `intent=`. Components should show as current and
   the gaps list should be empty, or hold only items you chose to skip and
   will tell the user about. Commit the docstrings, `intent.json` and
   `atlas.md` together.

## intent.json

```json
{
  "summary": "Billing service for the storefront.",
  "components": {
    "billing": {
      "purpose": "Creates invoices and records payments. Does not talk to the payment gateway directly.",
      "fingerprint": "0b6807b28679",
      "patterns": ["Ports and adapters"]
    }
  },
  "patterns": [
    {
      "name": "Ports and adapters",
      "description": "Domain code calls abstract gateways; adapters implement them for each provider.",
      "components": ["billing", "gateways"]
    }
  ]
}
```

## Rules

- Read a module's source before you describe it. Do not infer from names.
- Describe responsibility and boundaries, not implementation steps or history.
- Change docstrings and `intent.json` only. Never change code behavior. Do not
  edit the hints file (`sysatlas.json`) unless the user asks.
- If the atlas shows an import cycle, a spec violation, or a component that
  looks like two things, tell the user. Do not hide it in prose.
- If the hints file has an `architecture` spec, the atlas reports whether the
  code conforms. Report violations; do not edit the spec to remove them unless
  the user asks.
- Do not invent a pattern to fill space.
