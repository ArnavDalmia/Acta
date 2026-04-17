When working on this project, use the Acta development ledger tools:

- At the start of a task, call acta_start_session and acta_append_entry with type "intent"
- When making architectural choices, log a "decision" entry
- When trying something uncertain, log "experiment" then "result"
- When you identify something to do later, log a "todo"
- When something is blocking progress, log a "blocker"
- Before committing, log a "commit_summary"
- Use acta_get_recent_context to recall what happened recently
- Use acta_get_open_items to check pending todos and blockers
