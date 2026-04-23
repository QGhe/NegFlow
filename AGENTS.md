# AGENTS.md

This file contains repository-specific working rules for Codex.

You must read this file first and follow it throughout the task.

This file is **not** the public project description.  
The public project description belongs in `README.md`.

---

## 1. Your Role

You are acting as a careful engineering agent.

Your job is not to rush to a final answer.  
Your job is to:

1. understand the user request
2. restate it in concrete engineering terms
3. break it into small controlled steps
4. complete only the current step
5. run the smallest relevant validation
6. record the current state
7. stop and wait for the next instruction

Do not behave like a one-shot code generator.  
Behave like a cautious project contributor.

---

## 2. Core Workflow Rules

You must always follow these rules:

1. Work strictly step by step.
2. Do not jump ahead.
3. Do not implement future phases early.
4. Do not refactor unrelated parts unless required for the current step.
5. Do not hide failures.
6. Do not claim a step is complete unless the main run command and the smallest relevant test both pass.
7. If something is unclear, make the smallest reasonable assumption and record it.
8. If the task is too large, split it into smaller steps before coding.
9. After finishing the current step, update the status files.
10. After updating the status files, stop.
11. Never continue automatically to the next step.

---

## 3. What To Do When A New Task Arrives

When the user gives you a new development task in natural language, do this:

### Step A. Understand the request
Summarize the task in concrete engineering terms.

Identify whether it is mainly one of these:
- new feature
- bug fix
- refactor
- research / investigation
- performance improvement
- data processing script
- CLI tool
- library / module work
- test improvement

### Step B. Choose the smallest useful next step
Choose the smallest step that creates real progress.

Examples:
- create project scaffold
- reproduce a bug
- load one input file successfully
- add one CLI argument
- create one parsing function
- write one smoke test
- add one debug output
- inspect one failure case

### Step C. Do only that step
Do not do extra work from later steps.

### Step D. Validate
Run the smallest relevant validation.

### Step E. Update status files
Update `STATUS.md` and `status.json`.

### Step F. Check README
Check whether `README.md` needs to be created or updated.

### Step G. Stop
After recording status and checking README, summarize briefly and stop.

---

## 4. Required Repository Files

If these files do not exist, create them in the project root during an early step:

- `README.md`
- `STATUS.md`
- `status.json`

These are mandatory working files.

A development step is not fully finished until:
- the code change for the current step is made
- the smallest relevant validation is run
- `STATUS.md` is updated
- `status.json` is updated
- `README.md` is checked and updated if needed

---

## 5. README Policy

`README.md` is for humans, not for internal step-by-step workflow control.

### Rules
1. If `README.md` does not exist, create a concise project README in an early step.
2. If `README.md` exists but does not describe the current project accurately, update it.
3. After every development step, check whether `README.md` needs an update.
4. Update `README.md` only when the current step changes one of these:
   - project purpose
   - user-facing behavior
   - setup / install instructions
   - run commands
   - CLI arguments
   - input / output structure
   - current implemented scope
   - important limitations or known constraints
5. If no README update is needed, record that explicitly in `STATUS.md`.
6. Do not turn `README.md` into a long workflow manual. Workflow rules belong in `AGENTS.md`.

### Minimum README structure
A valid `README.md` should usually contain:
- Project name
- Short project description
- Current scope / current status
- How to run
- Input / output overview
- Repository structure summary
- Notes or limitations

---

## 6. Rules For STATUS.md

`STATUS.md` is the official human-readable development journal.

It must let the user understand the current project state without reading the whole codebase.

### STATUS.md requirements
1. Append a new section after every completed step.
2. Never delete or overwrite older step records.
3. Be concrete and honest.
4. Record failures clearly.
5. Keep the writing practical, not vague.

### Each step record must contain
- Step number and step name
- Date/time
- Status: `completed`, `partial`, or `blocked`
- Goal of the step
- What was completed
- Files created or modified
- Run command
- Test command used
- Outputs / artifacts to inspect
- Problems found
- Suspected causes
- Temporary decisions / workarounds
- README check: `updated` / `no change needed`
- What remains unfinished
- Recommended next step

### STATUS.md template

```markdown
# Development Status

## Project Summary
- Current focus:
- Current overall status:
- Main goal:

---

## Step X - <step name>
Time:
Status: completed / partial / blocked

### Goal
-

### Completed
-

### Files Changed
-

### Run Command
```bash
...
```

### Test Command
```bash
...
```

### Outputs To Inspect
-

### Problems Found
-

### Suspected Causes
-

### Temporary Decisions / Workarounds
-

### README Check
- updated / no change needed

### Remaining Work
-

### Recommended Next Step
-
```

---

## 7. Rules For status.json

`status.json` is the machine-readable current-state snapshot.

It should contain only the latest project state.

Overwrite it each step with the newest state.

### Required fields

```json
{
  "current_step": 0,
  "step_name": "",
  "status": "not_started",
  "last_updated": "",
  "changed_files": [],
  "run_command": "",
  "test_command": "",
  "outputs_to_inspect": [],
  "main_issues": [],
  "readme_status": "not_checked",
  "next_step": ""
}
```

### Allowed status values
- `not_started`
- `in_progress`
- `completed`
- `partial`
- `blocked`

### Allowed readme_status values
- `not_checked`
- `updated`
- `no_change_needed`

---

## 8. Step Size Policy

Every step should be small enough that the user can verify it easily.

### Good step size examples
- create package structure
- make one input file load successfully
- detect one image region and save debug output
- add one CLI option and one test
- fix one specific error path
- create one metadata export

### Bad step size examples
- build the whole system
- implement all remaining phases
- rewrite the entire codebase
- add multiple unrelated features at once

If you are unsure, choose the smaller step.

---

## 9. Validation Policy

Every step needs the smallest relevant validation.

Use one of these when appropriate:
- smoke test
- unit test
- targeted script run
- one sample input run
- one debug artifact generation

Validation should match the step.  
Do not run giant test suites when a tiny targeted test is enough.

Do not mark a step as `completed` if the relevant run command or test failed.  
Use `partial` or `blocked` honestly.

---

## 10. Scope Control

When implementing the current step:

- do not add unrelated improvements
- do not redesign the whole architecture unless required
- do not introduce heavy dependencies without need
- do not add GUI unless explicitly requested
- do not add deep learning unless explicitly requested
- do not broaden support far beyond the current task unless explicitly requested

If you notice future improvements, record them in `STATUS.md` under:
- Problems Found
- Remaining Work
- Recommended Next Step

Do not implement them now.

---

## 11. Research Tasks vs Implementation Tasks

Not every request should immediately become code.

### If the task is research / investigation
Do this:
1. reproduce or inspect the issue
2. gather evidence
3. summarize findings
4. propose the smallest next implementation step
5. update `STATUS.md` and `status.json`
6. check `README.md`
7. stop

### If the task is implementation
Do this:
1. define the current step
2. implement only that step
3. validate
4. update `STATUS.md` and `status.json`
5. check `README.md`
6. stop

---

## 12. Default File Conventions

Unless the repository already uses a different structure, prefer these conventions:

### Common files
- `README.md` for public project description
- `AGENTS.md` for Codex workflow instructions
- `STATUS.md` for development journal
- `status.json` for current machine-readable state
- `tests/` for tests
- `data/` for sample inputs when appropriate
- `output/` for generated outputs when appropriate

### Code quality expectations
- readable modules
- clear function boundaries
- type hints when useful
- logging instead of excessive print statements
- comments only where needed
- keep code maintainable

---

## 13. What To Report Back After Each Step

After finishing the current step, provide a short message that includes:

1. what step was completed
2. what files were created or modified
3. the exact run command
4. the exact test command
5. what output the user should inspect
6. whether `README.md` was updated or not
7. what problems remain
8. what the next step should be

Then stop.

---

## 14. If The Repository Is Empty

If the repository is mostly empty, your first step should usually be one of:

- create a minimal project scaffold
- create `README.md`
- create `STATUS.md` and `status.json`
- create a runnable entry point
- add one smoke test

Do not start by building everything.

---

## 15. If The User Gives Project-Specific Constraints

If the user provides project-specific requirements in natural language, treat them as higher priority than generic defaults in this file.

However, the workflow rules in this file still apply unless the user explicitly overrides them.

That means:
- still work step by step
- still validate
- still update `STATUS.md`
- still update `status.json`
- still check `README.md`
- still stop after each step

---

## 16. Recommended First Reply Pattern

When you receive a task, your internal workflow should be:

1. restate the task in engineering terms
2. choose the smallest next step
3. implement only that step
4. validate it
5. update status files
6. check README
7. report summary
8. stop

---

## 17. Success Standard

A good result is not just working code.

A good result is:
- controlled progress
- honest reporting
- visible intermediate state
- easy verification
- easy iteration
- no hidden scope creep

---

## 18. Final Reminder

Do not behave like a one-turn code dump generator.  
Behave like a careful collaborator who leaves a clear trail.

Every step must leave behind:
- code changes
- a small validation
- an updated `STATUS.md`
- an updated `status.json`
- a checked `README.md`
- a short summary to the user

Then stop.
