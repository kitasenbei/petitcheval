# petitcheval — project task tracker

Use `python -m petitcheval` to manage project tasks. All CLI output is JSON.

## Quick reference

```bash
# See everything in one call
petitcheval dump [--workspace <name|id>]

# Workspaces (one per project)
petitcheval workspace list
petitcheval workspace add <name>

# Tasks (features/efforts within a workspace)
petitcheval task list --workspace <name|id>
petitcheval task add <name> --workspace <name|id>
petitcheval task start <id>          # mark in_progress
petitcheval task done <id>           # mark done

# Steps (checklist items within a task)
petitcheval step add <text> --task <id> [-p high|medium|low] [--note <context>]
petitcheval step done <id>
petitcheval step note <id> <text>    # attach context for next session
```

## Workflow

1. At the start of a session, run `petitcheval dump --workspace <name>` to see current state
2. Before starting a feature, run `petitcheval task start <id>` to mark it in_progress
3. Break work into steps with `petitcheval step add`
4. Use `--note` on steps to leave context for future sessions (blockers, file references, decisions)
5. Mark steps done as you complete them
6. When all steps are done, run `petitcheval task done <id>`
