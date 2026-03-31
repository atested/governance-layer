1. PURPOSE

Set up Tailscale CLI integration on this Mac so the `tailscale` command is available on PATH for Terminal/Codex use, or stop with the exact local-machine blocker if bounded setup cannot be completed.

2. PRECHECK_RESULT

- `pwd` matched the required execution root: `/Volumes/SSD/archive/gov/governance-layer`
- Tailscale.app was present on this Mac at `/Applications/Tailscale.app`
- `tailscale` was not present on PATH before setup
- Unrelated worktree items were preserved and not touched:
  - `.claude/agents/sonnet-worker.md`
  - `run-operator-ui.sh`

3. TAILSCALE_APP_FINDINGS

- Actual discovered app path:
  - `/Applications/Tailscale.app`
- Actual discovered usable CLI target path:
  - `/Applications/Tailscale.app/Contents/MacOS/Tailscale`
- Supporting app-bundle resources present:
  - `/Applications/Tailscale.app/Contents/Resources/InstallTailscaleCLI.scpt`
  - `/Applications/Tailscale.app/Contents/Resources/UninstallTailscaleCLI.scpt`
- Direct CLI target verification:
  - `/Applications/Tailscale.app/Contents/MacOS/Tailscale version` worked and reported `1.94.1`

4. CLI_INTEGRATION_ACTION_TAKEN

- Chosen integration shape:
  - symlink at `/usr/local/bin/tailscale`
- Attempted action:
  - `ln -s /Applications/Tailscale.app/Contents/MacOS/Tailscale /usr/local/bin/tailscale`
- Result:
  - blocked
- Why:
  - `/usr/local/bin` is not writable by the current user in this session
  - the symlink creation failed with `Permission denied`
- No wrapper was created because the direct app-bundle executable is a valid CLI target and a wrapper was not required.

5. VERIFICATION

- `tailscale` on PATH before setup:
  - absent
- Direct app-bundle CLI verification:
  - `YES`
- `tailscale version` through PATH after attempted setup:
  - `NO`
- Truthful result:
  - CLI target was discovered, but PATH integration was not installed because the required write to `/usr/local/bin/tailscale` was blocked by local permissions.

6. BLOCKER_IF_ANY

The exact blocker is local write permission for `/usr/local/bin/tailscale`. Creating the required symlink failed with:

`ln: /usr/local/bin/tailscale: Permission denied`

This setup now requires an admin-authorized write to `/usr/local/bin` on this Mac.

7. STOP_BOUNDARIES

- Stopped after the minimum truthful integration attempt.
- Did not proceed into Funnel setup.
- Did not guess alternate launcher paths or modify unrelated system configuration.
