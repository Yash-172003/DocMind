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
