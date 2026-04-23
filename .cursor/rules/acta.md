When working on this project, use the Acta development ledger tools:

- At the start of a task, call acta_start_session and acta_append_entry with type "intent"
- When making architectural choices, log a "decision" entry
- When trying something uncertain, log "experiment" then "result"
- When you identify something to do later, log a "todo"
- When something is blocking progress, log a "blocker"
- Before committing, log a "commit_summary"
- Use acta_get_recent_context to recall what happened recently
- Use acta_get_open_items to check pending todos and blockers
- If invoked by Cursor/Claude/VSC Agent, self-report your model name from context on every acta_append_entry call (model field) and on every acta_record_cost call

Cost tracking (required — do this on every response):

- At the end of each response, call acta_record_cost with the project_id, your model name, and your token usage for this turn
- Prefer real token counts from the runtime/tool context when available (e.g. usage.input_tokens / usage.output_tokens)
- If real counts are not exposed, ESTIMATE them from text length using ~4 characters per token:
  - tokens_in ≈ ceil(len(input_context_chars) / 4)
  - tokens_out ≈ ceil(len(response_chars) / 4)
  - Round each to the nearest whole number; never pass negative values
- Pass session_id whenever you have one (returned by acta_start_session) so per-session cost rollups in the Token Usage tab stay accurate
- One acta_record_cost call per response is enough — do not split a single turn into many rows
