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

## 2026-07-10 — Phase 0, Week 3-4

**What I built:** A production-grade async FastAPI architecture with SQLAlchemy, Alembic, Dependency Injection, and Background Tasks.

**What I learned:** 
We updated our `config.py` file which added `database_url` and `api_key` to the Pydantic Settings class cause hardcoding it in our code is a security risk. So this file reads the `.env` file and checks if the variables are missing or wrong and crash the app immediately.

Now, we also created the `base.py` file which acts as the bridge between our FastAPI app and PostgreSQL. It has the `create_async_engine` which is the actual connection to the PostgreSQL. It also has `async_sessionmaker` which helps us create a session for each API call.

We created `models.py` too which defines what our db tables are gonna look like. It uses SQLAlchemy which is the translator between the python code and the sql db and allows us to create python object and classes instead of sql strings. This is what ORM means - Object Relational Mapping. Every table created will inherit from the Base class. We also have the `DocumentStatus` class which has defined 4 states - pending, processing, done, failed. We also have the `Document` class which basically gets the filename, uuid, status, created_at, updated_at etc.

We have created `env.py` which has Alembic. It is a db migration tool. So, basically `models.py` is like a blueprint and Alembic is the one who reads the blueprint and builds and modifies the actual db. Let's say we altered a Python class (like adding a new column), Alembic detects the difference between the code and the live db and then automatically generates the Python migration scripts required to update the db schema. For our project it compares by checking what's in `Base.metadata` and PostgreSQL. One of the core problems this file solves is that Alembic is built for synchronous SQLAlchemy and our app is async. So, it bridges this gap. `connection.run_sync(do_run_migrations)` is the bridge. It takes the synchronous migration function and runs it through the async connection. We can think of it as an adapter - async engine on one side, sync migration code on the other, `run_sync` in the middle making them compatible. It can also run in two modes - offline and online too.

Now, we also have `deps.py` which defines two things our FastAPI endpoints will need on almost every request - a db session and authentication. We are using dependency injection and it is a very important concept too. FastAPI sees the `Depends(get_db)` and `Depends(verify_api_key)`, and runs those functions automatically before any endpoint even starts. The `get_db` function is a thin wrapper around `get_async_session` for testability for when we write tests for later. In the `verify_api_key` function we are using `Security()` which works like `Depends()` but is security-related. And then its just simple logic, if the header is missing — api_key is None — reject. If it does not match your configured key in `.env` — reject. Otherwise return the key and let the request continue.

We also have `document.py` in the schema folder which basically defines our response model. We dont want to return raw ORM models from our API but instead want to define a explicit response that has a fixed schema.

We have `documents.py` in the endpoints folder which contains the actual HTTP routes for our app - our real API. So, the user can upload a doc and immediately get a job id back, and then can poll for the status while processing happens in the bg. The four concepts here used are - 1) Models from `models.py` 2) Sessions from `deps.py` 3) Dependency injection from `deps.py` 4) Async bg tasks. The `simulate_document_processing` function with `asyncio.sleep(3)` is a placeholder — Phase 1 replaces it with real PDF extraction.

In the `main.py` file, we added lifespan event which ensures clean startup and close ups of the db engine. We also added a global_exception_handler to handdle any random python error and officially mounted the router for our document endpoints.

In the `test_documents.py` file, we simulated a client uploading a fake file, checking the status, reading and then deleting the content too. This serves as an integration test to see if everything works together perfectly fine.

Now we also encountered a asyncio error too. What happened is:

```text
event loop      (all async operations)
      ↑
connected (created by)
      ↑
async engine → "pool of connections" to PostgreSQL
      └─ (pre-opened connections)

But, pytest-asyncio → new event loop for each test

So:

async engine
      ↓
created by event loop
      ↓
shared across tests
      ↓
event loop from test 1 was destroyed
      ↓
test 2 inherited an engine pointing to a dead loop
```

So, for the fix: setting `asyncio_default_test_loop_scope = "session"` gives all tests one shared loop so the pool stays alive and valid throughout.

---

## 2026-08-19 — Phase 0, Week 5-6

**What I built:** Expanded the database schema with a `chunks` table, JSONB metadata, pgvector embeddings, four custom indexes, connection pooling, and verified everything with EXPLAIN ANALYZE.

**What I learned:**

From what I have understood, earlier our `Document` table was only storing information about the document itself, but now it can support chunking, embeddings, and metadata filtering.

In `models.py`, we added two new fields to the `Document` model. The first one is `metadata_`. Some files may have page counts, authors, languages, file sizes, and other files may have completely different information. Instead of creating a new database column for every possible property, JSONB lets us store all of that in a schema-less format. We also added `chunk_count`, storing the value directly in the document row so we can read it instantly without doing extra joins or running a `COUNT(*)` query every time.

We also created a completely new `Chunk` table. From what I understood, this is where the real content of our documents lives. Every chunk belongs to one document through the `document_id` foreign key. We also enabled `ondelete="CASCADE"`, which means if a document gets deleted, PostgreSQL automatically deletes all its chunks too, without us having to manually clean them up. The `chunk_index` tells us the order of the chunk inside the document. The `text` column stores the extracted content itself. We also added `token_count` and `page_numbers` to the chunk model.

Now, we also created a relationship called `document.chunks`. This is a one-to-many relationship because one document can have many chunks. We configured it with `cascade="all, delete-orphan"`, and from what I understood, while PostgreSQL handles deletes at the database level through the foreign key, SQLAlchemy can also automatically manage related chunk objects when operations happen through the ORM. Basically, both the database and the Python layer are working together to keep the data clean and synchronized.

Another thing we did was create multiple indexes. Before this, I mostly thought indexes were just used to make queries faster, but here I learned that different index types solve completely different query patterns. The status index helps queries like finding all completed documents. The composite index on `document_id` and `chunk_index` is interesting because it can satisfy both filtering and sorting from a single index. Finally, the HNSW index is specifically designed for vector similarity search.

In `base.py`, we improved our database connection pooling, and what I learned is that creating a new database connection every time an API request arrives is expensive. So SQLAlchemy maintains a pool of reusable connections. We set `pool_size=5`, which means five connections stay ready at all times. `max_overflow=10` allows temporary extra connections during heavy traffic, bringing the maximum to fifteen. `pool_timeout=30` tells requests to wait up to thirty seconds before failing if every connection is busy.

In `document.py`, we updated our response schemas. The `DocumentResponse` model now exposes the new `metadata_` and `chunk_count` fields. We also created a new `ChunkResponse` model.

We also added a new endpoint called `GET /documents/{id}/chunks`.

We also created a standalone script called `explain_queries.py`. This was mainly used to verify that PostgreSQL was actually using the indexes we designed. The script generated 100 documents and 1000 chunks with random 1024-dimensional vectors and then ran `EXPLAIN ANALYZE` on different query patterns. From what I understood, this is an important validation step because creating an index does not automatically mean PostgreSQL will use it.

Finally, we updated `pyproject.toml`. We added `numpy` and `pgvector` because they are required for vector-related operations.

---

## 2026-08-19 — Phase 0, Week 7-8

**What I built:** Containerized the FastAPI app itself with a multi-stage Dockerfile, added it to docker-compose, and added a full self-hosted Langfuse observability stack.

**What I learned:**

The biggest thing I learned was how a multi-stage Docker build works. We created a common base stage which acts as the foundation for both development and production environments. One important optimization here is that Docker caches layers. As long as dependencies remain unchanged, it simply reuses the cached layer.

We also fixed the import issue inside Docker by setting `PYTHONPATH=/app/src`. Since our project is not actually installed as a Python package inside the container, Python needs to be explicitly told where the `docmind` package exists.

We then created two separate environments. The development stage installs all development tools, allowing code changes on our machine to instantly reflect inside the container. The production stage only installs what is needed to run the application and excludes development dependencies.

We also created a `.dockerignore` file to prevent unnecessary files and sensitive information from being sent into the Docker build process.

In `docker-compose.yml`, we added a new `app` service which builds the development version of the Docker image. One important thing I learned is that containers communicate using service names rather than `localhost`. This is why the application uses `db:5432` to connect to PostgreSQL when running inside Docker. We also configured health checks so the application waits until PostgreSQL and Redis are actually ready before starting.

Another major addition was the complete Langfuse stack, and it consists of multiple services working together. It has its own web application, worker service, PostgreSQL database, Redis queue, ClickHouse analytics database, and MinIO object storage. Each component has a specific responsibility, and keeping them separate avoids conflicts with our own application infrastructure.

We also configured persistent volumes for all major services. From what I understood, these volumes act like virtual disks that survive container restarts, ensuring that databases and application data are not lost whenever containers are recreated.

Finally, we encountered an issue with ClickHouse. The application kept crashing because Langfuse automatically assumed a clustered ClickHouse setup when a specific configuration variable was missing. Cluster mode requires Zookeeper, which we were not running. The fix was to explicitly disable cluster mode, which allowed ClickHouse to run as a standalone instance. This taught me that some configuration flags may look optional but can completely change how a system behaves internally.

---
