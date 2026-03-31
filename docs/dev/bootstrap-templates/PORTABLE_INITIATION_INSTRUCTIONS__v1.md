# Portable Initiation Instructions v1

**What this is:** Step-by-step instructions for starting a new governed development project from seed material. Follow these steps in order. You do not need to remember the details of the bootstrap protocol — these instructions guide you through each action.

**When to use this:** When you have identified content in any chat, project, or document that is worth turning into its own governed development project.

**Protocol version:** NEW_PROJECT_BOOTSTRAP_PROTOCOL v1

---

## Prerequisites

Before you begin, confirm:

- You have a ChatGPT account with the ability to create projects.
- You have a GitHub account with the ability to create repos.
- You have access to a Cecil-capable session (governance-layer repo or equivalent).
- You have identified seed material that contains at least one concrete thing to build (not just discussion or exploration).

---

## Steps

### Step 1: Copy the seed content

Copy or export the relevant seed content from wherever you found it. This can be:

- a ChatGPT chat transcript (full or partial)
- notes from a document or conversation
- code sketches, architectural decisions, or constraint lists

You do not need to clean or restructure the content. Copy the parts that contain the project-forming material. You can provide it in multiple chunks later if it is large.

**Where you are now:** Any project, any chat, any document. This step is portable.

### Step 2: Create the destination GPT project

Go to ChatGPT and create a new project:

1. Open ChatGPT project management.
2. Create a new project with a working name for your new project.
3. Create a new chat inside that project.

**Where you are now:** The new destination project, in a new empty chat.

### Step 3: Paste the start block

Paste the following block as the first message in the new chat. Replace `{PROJECT_WORKING_NAME}` with your project's working name.

> Copy the contents of `DESTINATION_WORKING_CHAT_START_BLOCK__v1.md` and paste it into the chat, filling in the project working name.

The start block is available at:
`docs/dev/bootstrap-templates/DESTINATION_WORKING_CHAT_START_BLOCK__v1.md`
in the governance-layer repo.

**What should happen:** ChatGPT acknowledges bootstrap mode and tells you it is ready to receive seed content.

**If this does not happen:** Re-paste the start block. If ChatGPT still does not acknowledge bootstrap mode, check that the block was pasted completely.

### Step 4: Paste the seed content

Paste the seed content you copied in Step 1 into the chat.

- If the content is large, paste it in labeled chunks (e.g., "Seed Part 1 of 3") and tell ChatGPT how many parts to expect.
- If you have operator notes or constraints that are not part of the seed content itself, prefix them with `OPERATOR NOTES:` so ChatGPT routes them to the correct field.

**What should happen:** ChatGPT processes the seed content and produces a Seed Package — a structured summary of the project with extracted fields, preserved source excerpts, and a preliminary screening result.

**If ChatGPT asks clarifying questions:** Answer them. ChatGPT may need clarification to fill in required fields (project name, scope, deliverable type, at least one concrete task).

### Step 5: Review the Seed Package

ChatGPT presents the Seed Package for your review.

Check:
- Does the `project_name` look right?
- Does the `scope_statement` accurately describe what you intend to build?
- Are the `key_constraints` correct?
- Do the `initial_task_candidates` represent real work you want done?
- Did ChatGPT preserve important source excerpts that contain ambiguity or unresolved questions?

If anything is wrong, tell ChatGPT what to fix. ChatGPT will produce an updated Seed Package (v2, v3, etc.) with the correction.

### Step 6: Review the preliminary screening result

ChatGPT includes a preliminary screening result in the Seed Package.

- If **PASS**: ChatGPT produces a Cecil Evaluation Dispatch. Proceed to Step 7.
- If **FAIL**: ChatGPT produces a Preliminary Deficiency Report listing what is missing. Provide the missing information, and ChatGPT will re-screen.

Preliminary screening checks structural completeness only (scope, tasks, naming, constraints). It does not judge whether the project is architecturally sound — that is Cecil's job.

### Step 7: Deliver the Cecil Evaluation Dispatch to Cecil

ChatGPT produces a Cecil Evaluation Dispatch containing the Seed Package and screening notes.

1. Copy the entire Cecil Evaluation Dispatch from the chat.
2. Open a Cecil session (governance-layer repo or any Cecil-capable context).
3. Paste the dispatch to Cecil.

**What should happen:** Cecil evaluates the Seed Package for promotability and returns one of:

- **PROMOTE** + an Approved Bootstrap Plan — proceed to Step 8.
- **REVISE** + specific deficiencies — return to the destination working chat, provide the missing information, get an updated Seed Package, and re-dispatch to Cecil.
- **REJECT** + stated reasons — the seed is not viable for project creation. Cecil explains why.

### Step 8: Create the GitHub repo

Cecil has approved the bootstrap. Now create the repo:

1. Go to GitHub and create a new repo with the project name from the Approved Bootstrap Plan.
2. Clone it locally to your preferred path.
3. Tell Cecil the repo URL (`repo_remote`) and local path (`repo_root`).

Cecil will create the PROJECT_IDENTITY.md file and commit it as the repo's first commit.

**What should happen:** Cecil confirms the identity binding commit is pushed. The repo now has one commit with PROJECT_IDENTITY.md.

### Step 9: Return to the destination chat for Codex dispatch

Go back to the destination working chat in ChatGPT.

1. Tell ChatGPT that Cecil approved the bootstrap and provide the Approved Bootstrap Plan.
2. Tell ChatGPT the repo URL and local path.
3. ChatGPT produces a Codex Bootstrap Dispatch.
4. Run the dispatch in Codex.

**What should happen:** Codex creates a bootstrap branch with all dev-process governance files.

### Step 10: Activation

1. Deliver the Codex result to Cecil (paste the completion packet to a Cecil session in the new repo).
2. Cecil merges the bootstrap branch and runs core activation tests.
3. If core activation passes: project status is **BOOTSTRAPPED**.
4. When ready, run one real task through the full dispatch/merge cycle.
5. If operational activation passes: project status is **ACTIVE**.

---

## Quick reference

| Step | Where | What |
|---|---|---|
| 1 | Anywhere | Copy seed content |
| 2 | ChatGPT | Create destination project + chat |
| 3 | Destination chat | Paste start block |
| 4 | Destination chat | Paste seed content |
| 5 | Destination chat | Review Seed Package |
| 6 | Destination chat | Check screening result |
| 7 | Cecil session | Paste Cecil Evaluation Dispatch |
| 8 | GitHub + terminal | Create repo, tell Cecil the URL/path |
| 9 | Destination chat | Get Codex dispatch, run in Codex |
| 10 | Cecil session (new repo) | Merge, activate |

## If something goes wrong

- **ChatGPT does not produce a Seed Package:** Re-paste the start block, then re-paste the seed content.
- **Preliminary screening fails:** Provide the missing information ChatGPT asks for. There is no limit on retries.
- **Cecil returns REVISE:** Address the specific deficiencies Cecil identified, update the Seed Package in the destination chat, and re-dispatch.
- **Cecil returns REJECT:** The seed is not ready for project creation. Cecil's reason explains what is missing. You may try again with different or expanded seed material.
- **Codex dispatch fails:** Check the dispatch against the Approved Bootstrap Plan. If the base SHA or allowlist is wrong, regenerate the dispatch in the destination chat.
- **Core activation fails:** Cecil reports which test failed. Fix the issue and re-run activation.
