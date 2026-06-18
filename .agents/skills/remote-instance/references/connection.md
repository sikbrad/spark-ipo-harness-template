# Remote Connection Reference

Read this when a task mentions "원격", "remote", SSH, a remote instance, or checking files under the same `/Users/gq/...` path on another machine.

## SSH Targets

This skill is self-contained and must not require an external connection-info file.

Default target: odung computer.

```bash
ssh -p 62001 gq@odungnest.iptime.org
```

When the user explicitly says `ax01` or `AX01`, use the AX01 company computer.

```bash
ssh -p 22 ax01@61.36.134.214
```

Use `scripts/remote_probe.sh --target ax01` for AX01. Use `scripts/remote_probe.sh --ssh '<ssh command>'` only when a user gives a target other than odung or AX01.

## Same-Location Path Convention

The local workspace is:

```text
/Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04
```

When a user says a file is at the "same location" or gives a `/Users/gq/...` path, verify whether that absolute path exists remotely before assuming a local-only target.

Use read-only probes first:

```bash
ssh -p 62001 gq@odungnest.iptime.org 'pwd; hostname; test -e /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 && echo exists'
```

For AX01:

```bash
ssh -p 22 ax01@61.36.134.214 'pwd; hostname; test -e /Users/gq/works/projs/dof-work-skills/dof-work-startpoint-04 && echo exists'
```

## Safety

- Prefer `ssh -o BatchMode=yes -o ConnectTimeout=8 ...` for probes so the command fails instead of hanging on password prompts.
- Do not run destructive remote commands unless the user explicitly requested that operation.
- For long remote jobs, write logs under `.omx/logs/` in the relevant workspace when practical.
