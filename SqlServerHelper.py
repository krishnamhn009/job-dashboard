import pyodbc
import pandas as pd
import logging
import asyncio
import aioodbc
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from time import sleep

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("sql_helper.log"), logging.StreamHandler()]
)

class SQLServerHelper:
    def __init__(self, server=None, database=None, username=None, password=None, driver="{ODBC Driver 17 for SQL Server}", max_retries=3, retry_delay=5):
        """Initialize SQL Server parameters for sync and async operations."""
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.driver = driver
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Sync
        self.conn = None
        self.cursor = None

        # Async
        self.pool = None

    # -------------------- SYNC METHODS -------------------- #
    def connect(self):
        """Establish sync connection with retries."""
        attempt = 0
        while attempt < self.max_retries:
            try:
                if self.username and self.password:
                    self.conn = pyodbc.connect(
                        f'DRIVER={self.driver};SERVER={self.server};DATABASE={self.database};UID={self.username};PWD={self.password}'
                    )
                else:
                    self.conn = pyodbc.connect(
                        f'DRIVER={self.driver};SERVER={self.server};DATABASE={self.database};Trusted_Connection=yes;'
                    )
                self.cursor = self.conn.cursor()
                logging.info("✅ Sync connection established")
                return
            except Exception as e:
                attempt += 1
                logging.error(f"Sync connection attempt {attempt} failed: {e}")
                sleep(self.retry_delay)
        raise Exception("❌ Max retries reached. Could not connect (sync)")

    def ensure_connection(self):
        """Reconnect sync connection if lost."""
        try:
            self.cursor.execute("SELECT 1")
        except:
            logging.warning("Sync connection lost. Reconnecting...")
            self.connect()

    def execute_query(self, query, params=None):
        """Execute sync SELECT query and return pandas DataFrame."""
        self.ensure_connection()
        try:
            logging.info(f"Executing sync query: {query} | Params: {params}")
            if params:
                df = pd.read_sql(query, self.conn, params=params)
            else:
                df = pd.read_sql(query, self.conn)
            logging.info(f"Query executed successfully, {len(df)} rows returned")
            return df
        except Exception as e:
            logging.error(f"Error executing sync query: {e}")
            raise

    def execute_non_query(self, query, params=None):
        """Execute sync INSERT/UPDATE/DELETE."""
        self.ensure_connection()
        try:
            logging.info(f"Executing sync non-query: {query} | Params: {params}")
            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
            self.conn.commit()
            rowcount = self.cursor.rowcount
            logging.info(f"Non-query executed successfully, {rowcount} rows affected")
            return rowcount
        except Exception as e:
            logging.error(f"Error executing sync non-query: {e}")
            self.conn.rollback()
            raise

    def execute_stored_procedure(self, proc_name, params=None):
        """Execute sync stored procedure."""
        self.ensure_connection()
        try:
            logging.info(f"Executing sync stored procedure: {proc_name} | Params: {params}")
            if params:
                placeholders = ",".join(["?"] * len(params))
                sql = f"EXEC {proc_name} {placeholders}"
                self.cursor.execute(sql, params)
            else:
                sql = f"EXEC {proc_name}"
                self.cursor.execute(sql)
            self.conn.commit()
            try:
                columns = [column[0] for column in self.cursor.description]
                rows = self.cursor.fetchall()
                df = pd.DataFrame.from_records(rows, columns=columns)
                logging.info(f"Stored procedure executed successfully, {len(df)} rows returned")
                return df
            except:
                logging.info("Stored procedure executed successfully, no results returned")
                return None
        except Exception as e:
            logging.error(f"Error executing sync stored procedure: {e}")
            self.conn.rollback()
            raise

    # -------------------- ASYNC METHODS -------------------- #
    async def async_connect(self, minsize=1, maxsize=5):
        """Create async connection pool."""
        dsn = f"DRIVER={self.driver};SERVER={self.server};DATABASE={self.database}"
        if self.username and self.password:
            dsn += f";UID={self.username};PWD={self.password}"
        else:
            dsn += ";Trusted_Connection=yes"
        self.pool = await aioodbc.create_pool(dsn=dsn, minsize=minsize, maxsize=maxsize)
        logging.info("✅ Async connection pool created")

    async def async_execute_query(self, query, params=None):
        """Execute async SELECT query and return DataFrame."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                logging.info(f"Executing async query: {query} | Params: {params}")
                await cur.execute(query, params or ())
                columns = [desc[0] for desc in cur.description]
                rows = await cur.fetchall()
                df = pd.DataFrame(rows, columns=columns)
                logging.info(f"Async query executed, {len(df)} rows returned")
                return df

    async def async_execute_non_query(self, query, params=None):
        """Execute async INSERT/UPDATE/DELETE."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                logging.info(f"Executing async non-query: {query} | Params: {params}")
                await cur.execute(query, params or ())
                await conn.commit()
                rowcount = cur.rowcount
                logging.info(f"Async non-query executed, {rowcount} rows affected")
                return rowcount

    async def async_close(self):
        """Close async connection pool."""
        self.pool.close()
        await self.pool.wait_closed()
        logging.info("✅ Async connection pool closed")

    # -------------------- AZURE KEY VAULT -------------------- #
    @classmethod
    def from_akv(cls, key_vault_url, secret_name_server, secret_name_db, secret_name_user=None, secret_name_pwd=None, driver="{ODBC Driver 17 for SQL Server}"):
        """Initialize helper using Azure Key Vault secrets."""
        try:
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=key_vault_url, credential=credential)

            server = client.get_secret(secret_name_server).value
            database = client.get_secret(secret_name_db).value
            username = client.get_secret(secret_name_user).value if secret_name_user else None
            password = client.get_secret(secret_name_pwd).value if secret_name_pwd else None

            return cls(server, database, username, password, driver)
        except Exception as e:
            logging.error(f"Error fetching secrets from AKV: {e}")
            raise

    # -------------------- CLOSE -------------------- #
    def close(self):
        """Close sync connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logging.info("✅ Sync connection closed")
