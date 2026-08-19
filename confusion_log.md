# Confusion Log

> "Treat confusion as information. Never move on from something broken without understanding why."

Record everything that didn't work as expected. Investigate. Write the resolution. Review monthly.

---

## Template

### [Date] — [Topic]
**What I expected:**
**What actually happened:**
**Why:**
**Resolution:**

---

### 2026-06-09 — Docker WSL 2 Backend Missing
**What I expected:** Docker Desktop to launch successfully after installation.
**What actually happened:** Docker crashed with: `The Windows Subsystem for Linux is not installed.`
**Why:** Windows requires WSL (Windows Subsystem for Linux) to run Linux containers natively. We installed Docker, but the host OS lacked the underlying Linux kernel interface.
**Resolution:** Open an **Administrator** PowerShell, run `wsl.exe --install`, and restart the machine.

<!-- Start logging above -->

### 2026-08-19 — Langfuse ClickHouse Crash Loop
**What I expected:** `langfuse-web` and `langfuse-worker` to start cleanly once ClickHouse, MinIO, Postgres, and Redis were all healthy — the official Langfuse compose reference lists `CLICKHOUSE_CLUSTER_ENABLED` alongside a bunch of other optional-looking feature flags (SMTP, Azure blob, OCI storage, LLM connection whitelisting) that we didn't set explicitly.
**What actually happened:** `langfuse-web` crash-looped on startup with `error: failed to open database: ... There is no Zookeeper configuration in server config` while trying to run `CREATE TABLE schema_migrations ON CLUSTER default (...) Engine=ReplicatedMergeTree`.
**Why:** The official reference file sets `CLICKHOUSE_CLUSTER_ENABLED: ${CLICKHOUSE_CLUSTER_ENABLED:-false}` explicitly. We left it unset assuming it was harmless. Without that explicit `false`, the Langfuse image's own internal default is clustered mode — which uses `ReplicatedMergeTree` table engines that require a Zookeeper ensemble for coordination. We never provisioned Zookeeper, so ClickHouse rejected the migration outright. Not every env var in a reference compose file is truly optional just because it has a `${VAR:-default}` fallback syntax — the fallback only applies if *we* omit the variable from our own file too; when we drop the line entirely, the image falls back to its own internal default, which can differ from the reference's default.
**Resolution:** Added `CLICKHOUSE_CLUSTER_ENABLED: "false"` explicitly to the `langfuse-worker`/`langfuse-web` shared environment block in `docker-compose.yml`, then recreated both containers. ClickHouse came up standalone and the migrations applied successfully.
