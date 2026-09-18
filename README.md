# sql2snowflake

One-shot copy of a SQL Server table into Snowflake, using pandas + `write_pandas`. Built for the AI group to stand up source data in Snowflake quickly so modeling work can start — not a production ETL job.

## What it does

1. Connects to SQL Server over ODBC using Windows integrated auth.
2. Counts and previews the source table so you can sanity-check before moving anything.
3. Connects to Snowflake via external browser SSO.
4. Streams the source table in chunks, normalizing column names, and writes each chunk with `write_pandas`.
5. Compares source and target row counts.

The script is written as `# %%` cells, so it runs top-to-bottom as a script or step-by-step in VS Code's interactive window.

## Setup

```bash
conda env create -f environment.yml
conda activate sql2snowflake
```

Requires an ODBC driver installed locally. The default is **ODBC Driver 17 for SQL Server** — change `ODBC_DRIVER` if you have 18 installed.

## Configure

Edit the settings block in `sql2snowflake.py`:

| Setting | Purpose |
|---|---|
| `SQL_SERVER`, `SQL_DATABASE`, `SQL_TABLE` | Source. `SQL_TABLE` is interpolated directly into the query — bracket-qualify it. |
| `ODBC_DRIVER` | Must match an installed driver name exactly. |
| `SF_ACCOUNT`, `SF_USER` | Snowflake account identifier and your SSO login. |
| `SF_ROLE`, `SF_WAREHOUSE`, `SF_DATABASE`, `SF_SCHEMA` | Target context. |
| `SF_TABLE` | Table to create. Date-suffix it (e.g. `Q_WK_DATA_20260917`) so reruns don't clobber a prior snapshot. |
| `CHUNK_ROWS` | Rows per batch. Lower it if you run out of memory. |

## Run

```bash
python sql2snowflake.py
```

A browser tab opens for Snowflake sign-in. On completion the script prints both row counts and whether they match.

## Behavior worth knowing

- **Reruns are destructive.** The first chunk is written with `auto_create_table=True` and `overwrite=True`, so re-running against the same `SF_TABLE` replaces it. That makes a failed run safe to retry, but it also means you can't append to an existing table without changing the flags.
- **Column names are rewritten.** Anything outside `A-Z`, `0-9`, `_` becomes `_`, names are uppercased, and a leading digit gets an underscore prefix. Your Snowflake columns will not match SQL Server verbatim.
- **Types are inferred by pandas**, not mapped from the source schema. Check the printed `dtypes` in the preview step before a large load. `use_logical_type=True` keeps dates and timestamps correct.
- **Full-table read.** There's no incremental or watermark logic — it's `SELECT *` every time.
- **Row count is the only validation.** It confirms nothing about column values or precision.

## Credentials

No secrets are stored in this repo. SQL Server uses `Trusted_Connection=yes` (your Windows identity) and Snowflake uses `externalbrowser` SSO. Do not add passwords or key-pair files to the repo — use environment variables or a local untracked config if you need them.

Note that `SF_USER` and `SF_ACCOUNT` are currently hardcoded. Move them to environment variables before anyone else uses this.

## Scope / not-goals

This is a developer-run landing utility. It is not scheduled, not idempotent against a live target, and not change-controlled. Anything that needs to run repeatedly or feed a production consumer should graduate to a proper Snowflake object under normal review and promotion.
