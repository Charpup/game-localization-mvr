# Glossary Directory

This directory contains the glossary lifecycle artifacts:

- pproved.yaml - Human-approved terms (source of truth)
- ejected.yaml - Rejected proposals (to avoid re-proposing)
- compiled.yaml - Runtime read-only (translate_llm reads this)
- compiled.lock.json - Version lock with hash
- conflicts_report.json - Generated when compile fails due to conflicts
