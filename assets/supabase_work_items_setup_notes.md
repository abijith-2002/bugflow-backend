# Supabase: Unified Work Items (Manual Setup Notes)

Because the automation RPC public.run_sql is not present in your project (PGRST202), please use the Supabase SQL Editor to apply the schema.

Required order:
1) Run assets/sql/projects_setup.sql
2) Run assets/sql/work_items_setup.sql
3) (Optional) Run assets/sql/tasks_bugs_setup.sql for counts in /projects

After running:
- Verify public.work_item exists with composite PK (project_id, id)
- Verify item_key is generated and unique
- Verify RLS is enabled and dev policies exist
- Verify trigger work_item_assign_incremental_id is attached

Backend endpoints that depend on this schema:
- GET /work-items?project_id=<uuid>
- POST /work-items

Troubleshooting:
- If /work-items POST returns 4xx: inspect Supabase error in the response; ensure constraints and trigger exist.
- If item_key is not set: check the generated column definition and that projects.project_key is populated for the given project_id.
- If id doesn't increment: ensure the trigger is present and function compiles without errors.

For production:
- Replace dev policies with policies based on auth.uid() and project membership.
- Consider creating enums for item_type/status/priority and adding update/delete policies.
