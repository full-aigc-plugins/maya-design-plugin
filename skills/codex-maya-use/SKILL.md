---
name: codex-maya-use
description: |
  Router for the Codex Maya plugin. When a Maya-related request does not match
  any of the dedicated Skills (`codex-maya-inspect`, `codex-maya-export-preview`,
  `codex-maya-diagnose`), this Skill routes the request to the appropriate
  one. Use it for ambiguous "open the Maya plugin" or "what should I do" prompts;
  do NOT use it for specific inspect / export / diagnose tasks — those have
  dedicated Skills with richer instructions.
---

# codex-maya-use

This is a thin router Skill. It does not perform any Maya work itself; it tells
the agent which of the dedicated Skills to invoke next.

## When to use

Invoke this Skill when the user says:

- "Open the Maya plugin"
- "What does the Maya plugin do?"
- "Use the Maya plugin to do X" (when X is not inspection, export, or diagnosis)

## Routing table

| User intent | Delegate to |
|---|---|
| Inspect a Maya scene (cameras, timeline, materials, references, namespaces, callbacks, unknown plug-ins) | `codex-maya-inspect` |
| Export a Maya Playblast preview (white-model, material-aware, or existing local video) | `codex-maya-export-preview` |
| Diagnose a Maya error, missing module, ABI mismatch, or path failure without installing software | `codex-maya-diagnose` |

## Anti-routing

If the user's request is already specific, **do not** call this Skill — call the
dedicated Skill directly. Calling `codex-maya-use` for a request that maps to
exactly one Skill wastes a turn and dilutes the description.

## Safety

This Skill never invokes Maya, never installs software, never modifies files
outside its own Skill directory. It returns routing text only.
