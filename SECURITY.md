# Security policy

## Supported versions

This project is at `0.1.0` and is developed on `main`. Fixes land on `main`;
there are no maintained release branches yet.

## Reporting a vulnerability

Please report suspected vulnerabilities privately rather than in a public issue.
Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository, or contact the maintainer directly.

Include the version or commit, a minimal reproduction, and the impact you
believe it has. You will get an acknowledgement, and credit in the fix if you
want it.

## Scope, stated honestly

This is important for triage: know what this package does **not** do.

- **No network surface.** The package makes no network calls. It does not start
  an MCP server, call a model provider, or talk to a remote host.
- **No credentials or accounts.** There is no authentication, no stored secret,
  and nothing to leak. Nothing here reads a token or an environment secret.
- **No persistence service.** A combat log is written only when a caller
  explicitly invokes `save_log` / passes `--log`. There is no scheduler,
  replication, background writer, or concurrency story.
- **Stdlib runtime.** The only dependencies are the development group and the
  optional `schema` extra (`jsonschema`).

The security-relevant boundary that does exist is **parsing untrusted input** —
loading a combat-encounter log. That path is designed to fail closed:

- loading is strict (`TypeError` for a wrong type, `ValueError` for a wrong
  value);
- payloads are bounded by entry count and byte size, so a hostile file cannot
  exhaust memory;
- an envelope *newer* than the reader is refused rather than guessed at;
- a resume reads the single file it was given and never scans a directory or
  follows a path out of the log.

The procedural audio writer emits WAV files to a caller-chosen location; it does
not execute or interpret the data it writes.

If you find a way to make the log loader accept malformed or adversarial input,
or to make a resume act on data it should have refused, that is exactly the class
of report that is in scope.
