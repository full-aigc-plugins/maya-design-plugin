---
name: maya-seedance-pipeline
description: Drive a Maya Playblast through the validated Dreamina 3D pipeline. Use when the user has a Maya scene and wants a Seedance 2.5 render from it.
metadata:
  type: workflow
  plugin: maya-design
  source_dcc: maya-design
  status: experimental
---

# maya-seedance-pipeline

> **Experimental — runtime gate `NOT_RUN`.** This Skill preserves fixture and
> contract compatibility only. It is not part of the current production
> release because no licensed Maya runtime has passed end-to-end acceptance.

## When to use

The user explicitly requests the experimental Maya path and understands that
its runtime acceptance is `NOT_RUN`. Do not route ordinary production requests
here.

## Workflow

Identical to `blender-seedance-pipeline` (partme-blender-plugin), but:

1. **Source DCC.** `maya-design` — preview mode defaults to `local_video`.
2. **Restore state.** Confirm the Maya adapter reports
   `restoration.status == 'confirmed'`. Reject otherwise.
3. **Camera.** Maya cameras often have `*Shape` suffixes; pass through the
   user-supplied camera name verbatim.

All other steps (validate → capability → quote → approve → submit →
query → download + verify) match the Blender workflow.

## Ledger transitions

Same machine as the Blender workflow: `Draft → DccSelected →
PreviewSpecified → PreviewValidated → CapabilityResolved → Quoted →
Approved → Submitted → Querying → Completed | Failed | Unknown`.

## Never do

- Never reuse a previous Playblast if the user has touched the scene
  since it was generated — invalidate the preview hash and re-export.
- Never send Maya scene data to the design plugin.
- Never auto-approve a quote.
