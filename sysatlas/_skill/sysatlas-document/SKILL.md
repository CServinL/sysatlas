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

4. **Patterns.** The atlas has already searched for the patterns that leave a
   structural footprint; they are in its "Pattern candidates" section. Go
   through the pattern checklist below, one row at a time, and give every row a
   verdict. Do not pick patterns from memory. Record only the rows with verdict
   `present` in `patterns` (name, one sentence on how it appears here, the
   components that take part).

5. **Summary.** Set `summary` to one short paragraph: what the system is for
   and who uses it.

6. **Verify.** Regenerate with `intent=`. Components should show as current and
   the gaps list should be empty, or hold only items you chose to skip and
   will tell the user about. Commit the docstrings, `intent.json` and
   `atlas.md` together. Give the user the list of `partial` verdicts from the
   checklist, each with its reason.

## Pattern checklist

The atlas has done a first search for rows marked **yes**. If the row's pattern
is in "Pattern candidates", read the modules in its evidence and decide. Rows
marked **no** are yours to search for: the atlas cannot see them.

A **missing** candidate means the detector found nothing, not that the pattern
is absent. The detectors need specific shapes (see "Detector limits"). For a
**yes** row with no candidate, spend a short look: check the module purposes and
the symbols in "Packages" for the pattern's vocabulary, and read the source only
if something suggests it.

For each row, give one verdict:

- `present` — all the evidence is there. Name the modules that show it.
- `partial` — some evidence, but not all. Say what is missing. Do not record
  it in `intent.json`; report it to the user.
- `absent` — no evidence. Say nothing more.

| Pattern | Atlas candidate | Evidence (all of it for `present`) |
|---|---|---|
| Layered | yes | Components fall into tiers, and no dependency points from a lower tier to a higher one. Import cycles weaken it |
| Pipeline | yes | Each stage passes its output to the next, and edges go one way. A chain of calls that return values to the caller is not a pipeline |
| Ports and adapters | yes | An abstract base class or protocol in core code, and concrete classes in separate modules that each import an external system. The core must not import those systems |
| Strategy | yes | One interface with several interchangeable implementations, and the caller picks one at run time |
| Facade | yes | One module that calls into several components and adds no logic of its own. A module of data models or constants is not a facade |
| Fluent builder | yes | Methods that return `self`, and a final call that builds, renders or saves |
| Plugin registry | yes | A registry, and several modules that register themselves with it or are found by name |
| Repository | yes | One class or module owns all reads and writes of a kind of data, and callers never touch the database library |
| Event-driven | yes | Publishers and subscribers share only an event type or a bus, not each other |
| Client and server | yes | A component that serves routes, and another component that calls it over HTTP |
| Command and task queue | yes | Entry points that are CLI commands or background tasks, each calling into the same core components |
| State machine | no | An explicit set of states, a transition table or function, and code that rejects invalid transitions |
| Dependency injection | no | Dependencies arrive through constructors or function arguments, not through module-level imports of concrete classes |
| Middleware chain | no | An ordered list of handlers that each wrap the next |

Detector limits (a pattern built another way gets no candidate):

- Ports and adapters, Strategy: need an abstract base class or `Protocol` in the
  scanned tree, with at least two implementations. Duck-typed interfaces are missed.
- Fluent builder: three or more public methods that always end in `return self`.
- Plugin registry: a public function named `register...` imported by two or more modules.
- Repository: a class named `*Repository`, `*Repo`, `*Store` or `*DAO` in a module that imports a database.
- Event-driven: a `publish` / `subscribe` function pair in one module, or a message-queue library.
- Layered: appears whenever there are three or more dependency tiers. Judge it
  by the import cycles and by whether lower tiers import higher ones.
- Pipeline: a chain of modules where each has one dependency and one dependent.
- Facade: a small module with high fan-in and fan-out. A model or constants module can match.

Rules for the checklist:

- Answer every row. A row you skipped is a row you did not check.
- A candidate is a lead, not a finding. Read the evidence modules before you
  say `present`; the atlas looked at structure only.
- Evidence means code you read, not names. A class called `Factory` is not a
  factory pattern.
- Atlas contradictions beat the pattern's name. An import cycle between two
  "layers" means the layered verdict is `partial` at best.
- Patterns that are not in the table (CQRS, saga, MVC, ...) may be recorded
  when the same standard of evidence is met. Say which modules show them.

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
- Do not invent a pattern to fill space. No evidence means `absent`.
