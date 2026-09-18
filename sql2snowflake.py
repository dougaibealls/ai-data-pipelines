# %% 1. Imports
import re
import time
import urllib.parse
 
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from sqlalchemy import create_engine, text
 
# %% 2. Settings
# SQL Server side
SQL_SERVER = "VPSCSQLRPTD02"
SQL_DATABASE = "MerchRPT"
SQL_TABLE = "[OUT].[Q_Wk_Data]"
ODBC_DRIVER = "ODBC Driver 17 for SQL Server"  # change to match your installed driver
 
# Snowflake side
SF_ACCOUNT = "X0000000000000-YYY00000"
SF_USER = "flast@beallsinc.com"
SF_ROLE = "BEALLS_AI_ARCHITECTURE"
SF_WAREHOUSE = "AI_WH"
SF_DATABASE = "DEV_BEALLS_AI"
SF_SCHEMA = "Q_REPORT" # adjust as needed
SF_TABLE = "Q_WK_DATA_20260917"  # table the script will create
 
CHUNK_ROWS = 50_000  # rows per batch; lower this if you run out of memory
 
 
def clean_column(name):
    # Uppercase and strip odd characters so Snowflake columns are easy to query
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name)).upper()
    return cleaned if not cleaned[0].isdigit() else f"_{cleaned}"
 
 
# %% 3. Connect to SQL Server (Windows login) and count source rows
odbc = (
    f"DRIVER={{{ODBC_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)
engine = create_engine("mssql+pyodbc:///?odbc_connect=" + urllib.parse.quote_plus(odbc))
 
with engine.connect() as conn:
    source_rows = conn.execute(text(f"SELECT COUNT(*) FROM {SQL_TABLE}")).scalar()
print(f"Source table has {source_rows:,} rows")
 
# %% 4. Preview the source data before moving anything
with engine.connect() as conn:
    preview = pd.read_sql(text(f"SELECT TOP 5 * FROM {SQL_TABLE}"), conn)
 
print(preview)
print("\nColumn types:")
print(preview.dtypes)
 
# %% 5. Connect to Snowflake (a browser tab opens for sign-in)
sf = snowflake.connector.connect(
    account=SF_ACCOUNT,
    user=SF_USER,
    authenticator="externalbrowser",
    role=SF_ROLE,
    warehouse=SF_WAREHOUSE,
    database=SF_DATABASE,
    schema=SF_SCHEMA,
)
print("Connected to Snowflake")
 
# %% 6. Copy the table in chunks (the long-running step; safe to rerun)
start = time.time()
loaded = 0
first = True
 
with engine.connect().execution_options(stream_results=True) as conn:
    for chunk in pd.read_sql(text(f"SELECT * FROM {SQL_TABLE}"), conn, chunksize=CHUNK_ROWS):
        chunk.columns = [clean_column(c) for c in chunk.columns]
 
        write_pandas(
            sf,
            chunk,
            table_name=SF_TABLE,
            auto_create_table=first,  # first batch creates the table
            overwrite=first,          # and replaces any earlier attempt
            use_logical_type=True,    # keeps dates/timestamps correct
        )
        first = False
        loaded += len(chunk)
        print(f"  loaded {loaded:,} of {source_rows:,} rows ({loaded / source_rows:.0%})")
 
print(f"Copy finished in {(time.time() - start) / 60:.1f} minutes")
 
# %% 7. Verify row counts
target_rows = sf.cursor().execute(f'SELECT COUNT(*) FROM "{SF_TABLE}"').fetchone()[0]
 
print(f"SQL Server rows: {source_rows:,}")
print(f"Snowflake rows:  {target_rows:,}")
print("Row counts match." if source_rows == target_rows else "ROW COUNTS DO NOT MATCH.")
 
# %% 8. Close connections
sf.close()
engine.dispose()
print("Connections closed")
