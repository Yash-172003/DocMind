# Learning Log

This file is a personal record of understanding. It captures my thoughts and takeaways in my own words at the moment of building.

---

## 2026-06-12 — Phase 0, Week 1

**What I built:** Scaffolded production-grade Python backend with uv, FastAPI, and strict typing

**What I learned:** From what I have understood, we have created multiple files here. The `main.py` file holds the main engine, where we have our FastAPI build. Also, we have our `pyproject.toml` file, which is like the backbone structure or blueprint of our application. It replaces the old `requirements.txt` file. So, it tells Python the dependencies we need, and `uv` is the tool which helps us read the blueprint and download them, which is much faster than the pip method. Now, we also have `ruff`, which is the Python formatter and linter that helps us with how the code looks and fixes errors/bugs automatically. It also has a dead code utility feature and a syntax modernizer too. We have `mypy` too, which helps us enforce fixed static type hints by checking them in our code. Now, we also have our `tests` folder which has the `test_main.py` file. It basically contains tests to check the health of the FastAPI app, as it is asynchronous and normal testing won't work.

---

## 2026-06-15 — Phase 0, Week 1

**What I built:** Implemented structured JSON logging via structlog

**What I learned:** For the things I understood about `structlog`, we have replaced normal "print" statements because normally it will become impossible for us to query the outputs if they are flat strings. So, we use `structlog` so we can instantly query it. It gives us timestamps, log levels, and also helps the output to be in JSON format on the server and a nice display for the user.

---

## 2026-06-22 — Phase 0, Week 2

**What I built:** Docker Compose infrastructure with PostgreSQL (pgvector) and Redis

**What I learned:** We created a `docker-compose.yml` file with two things. First, the `db` service which includes PostgreSQL and pgvector. This is for the storage of our embeddings so that we can search them semantically. It also has a volume called `postgres_data` which helps to save our data to a virtual disk. The important thing is that the data survives even if the container is deleted entirely — without a volume, if we stop Docker, the data is gone forever. It also runs a health check every 10 seconds. Second, the `redis` service is the cache part of our system. We enforced password authentication with it, and it has the same volume and health check pattern.

We also created two files: `.env.example` which stores the template of required variables, and `.env` which stores the actual passwords. The `.env` file is git-ignored, so real passwords are never committed to version history. `.env.example` exists as the way to tell other developers which variables they need to set up without exposing real secrets.

We also ran into an error because Pydantic was being strict about what it accepts — the new variables in `.env` like `POSTGRES_USER` didn't have matching fields in the `Settings` class, so it rejected them. We fixed this by adding `extra="ignore"` to tell Pydantic to silently skip variables it doesn't recognize rather than crashing the whole app.

---
