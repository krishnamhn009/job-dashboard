# job_dashboard_azure_akv.py
import streamlit as st
import pandas as pd
import asyncio
import aioodbc
import time
from datetime import datetime
from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient
from opentelemetry import trace, _logs
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.azure.monitor import AzureMonitorTraceExporter, AzureMonitorLogExporter
from opentelemetry.instrumentation.streamlit import StreamlitInstrumentor

# -----------------------
# Streamlit UI setup
# -----------------------
st.set_page_config(page_title="Job Dashboard Azure AKV", layout="wide")
col_title, col_refresh = st.columns([8, 1])
with col_title:
    st.title("📊 Job Execution Dashboard (Azure, AKV, Auto Refresh 1min)")
with col_refresh:
    if st.button("🔄 Refresh Now"):
        st.experimental_rerun()

# -----------------------
# Fetch secrets from AKV
# -----------------------
async def get_secret_from_akv(secret_name: str):
    kv_url = st.secrets["keyvault"]["url"]
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=kv_url, credential=credential)
    secret = await client.get_secret(secret_name)
    return secret.value

# Get SQL and App Insights connection strings
sql_conn_str = asyncio.run(get_secret_from_akv(st.secrets["keyvault"]["sql_secret_name"]))
app_insights_conn_str = asyncio.run(get_secret_from_akv("AppInsightsConnectionString"))

# -----------------------
# OpenTelemetry Azure Setup
# -----------------------
resource = Resource(attributes={SERVICE_NAME: "JobDashboardAzureAKV"})

# Tracer
tracer_provider = TracerProvider(resource=resource)
azure_trace_exporter = AzureMonitorTraceExporter(connection_string=app_insights_conn_str)
tracer_provider.add_span_processor(BatchSpanProcessor(azure_trace_exporter))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# Logger
logger_provider = LoggerProvider(resource=resource)
azure_log_exporter = AzureMonitorLogExporter(connection_string=app_insights_conn_str)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(azure_log_exporter))
_logs.set_logger_provider(logger_provider)
logger = _logs.get_logger("JobDashboardAzureAKVLogger", "1.0.0")

StreamlitInstrumentor().instrument()

# -----------------------
# Async SQL Connection
# -----------------------
async def get_sql_connection():
    conn = await aioodbc.connect(sql_conn_str, autocommit=True)
    return conn

# -----------------------
# Async DB Methods
# -----------------------
async def fetch_jobs():
    async with tracer.start_as_current_span("fetch_jobs"):
        conn = await get_sql_connection()
        async with conn.cursor() as cursor:
            query = """
            SELECT Client, JobID, JobName, Parameters, Status, Message,
                   ExecutedDateTime, RefNum, RetryCount
            FROM Jobs
            ORDER BY ExecutedDateTime DESC
            """
            await cursor.execute(query)
            rows = await cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
        await conn.close()
        df = pd.DataFrame(rows, columns=cols)
        return df

async def add_new_job(client, job_name, parameters):
    async with tracer.start_as_current_span("add_new_job"):
        conn = await get_sql_connection()
        async with conn.cursor() as cursor:
            query = """
            INSERT INTO Jobs (Client, JobName, Parameters, Status, Message, ExecutedDateTime, RefNum, RetryCount)
            VALUES (?, ?, ?, 'Pending', '', GETDATE(), NEWID(), 0)
            """
            await cursor.execute(query, (client, job_name, parameters))
        await conn.close()
        logger.info(f"Added new job: {job_name} for client {client}", extra={"client": client, "job_name": job_name})

async def retry_job(job_id):
    async with tracer.start_as_current_span("retry_job"):
        conn = await get_sql_connection()
        async with conn.cursor() as cursor:
            query = """
            UPDATE Jobs
            SET Status = 'Retry', RetryCount = RetryCount + 1, ExecutedDateTime = GETDATE()
            WHERE JobID = ?
            """
            await cursor.execute(query, job_id)
        await conn.close()
        logger.info(f"Job {job_id} marked for retry", extra={"job_id": job_id})

# -----------------------
# Add Job Section
# -----------------------
with st.expander("➕ Add New Job"):
    with st.form("add_job_form"):
        client = st.text_input("Client Name")
        job_name = st.text_input("Job Name")
        parameters = st.text_area("Parameters (comma-separated)")
        submitted = st.form_submit_button("Add Job")
        if submitted:
            if client and job_name:
                with st.spinner("Adding job..."):
                    asyncio.run(add_new_job(client, job_name, parameters))
                st.success("✅ Job added successfully.")
            else:
                st.warning("⚠️ Fill in all required fields.")

# -----------------------
# Fetch Jobs & Filters
# -----------------------
with st.spinner("Loading jobs..."):
    df = asyncio.run(fetch_jobs())

st.subheader("Filter Jobs")
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    filter_client = st.selectbox("Client", ["All"] + sorted(df["Client"].unique().tolist()))
with col2:
    filter_status = st.selectbox("Status", ["All"] + sorted(df["Status"].unique().tolist()))
with col3:
    filter_jobname = st.text_input("Job Name contains")
with col4:
    filter_ref = st.text_input("Reference Number")
with col5:
    filter_date = st.date_input("Executed Date", [])

# Apply filters
if filter_client != "All":
    df = df[df["Client"] == filter_client]
if filter_status != "All":
    df = df[df["Status"] == filter_status]
if filter_jobname:
    df = df[df["JobName"].str.contains(filter_jobname, case=False, na=False)]
if filter_ref:
    df = df[df["RefNum"].str.contains(filter_ref, case=False, na=False)]
if filter_date:
    df["ExecutedDateTime"] = pd.to_datetime(df["ExecutedDateTime"])
    if isinstance(filter_date, tuple) or isinstance(filter_date, list):
        start_date = pd.to_datetime(filter_date[0])
        end_date = pd.to_datetime(filter_date[1]) if len(filter_date) > 1 else start_date
        df = df[(df["ExecutedDateTime"].dt.date >= start_date.date()) & 
                (df["ExecutedDateTime"].dt.date <= end_date.date())]

# -----------------------
# Sorting
# -----------------------
st.subheader("Sort Table")
sort_column = st.selectbox("Sort by Column", df.columns.tolist())
sort_order = st.radio("Order", ["Ascending", "Descending"])
df = df.sort_values(by=sort_column, ascending=(sort_order=="Ascending"))

# -----------------------
# Display Table
# -----------------------
st.markdown("""
<style>
.scroll-container { overflow-x: auto; }
</style>
""", unsafe_allow_html=True)

with st.container():
    st.write('<div class="scroll-container">', unsafe_allow_html=True)
    for i, row in df.iterrows():
        cols = st.columns([1.2,1.2,1.5,2.5,1,2.5,1.5,1.2,1,1])
        cols[0].write(row["Client"])
        cols[1].write(row["JobID"])
        cols[2].write(row["JobName"])
        cols[3].write(row["Parameters"])
        cols[4].write(row["Status"])
        cols[5].write(row["Message"])
        cols[6].write(row["ExecutedDateTime"])
        cols[7].write(row["RefNum"])
        cols[8].write(row["RetryCount"])
        if cols[9].button("🔁 Retry", key=f"retry_{row['JobID']}"):
            with st.spinner(f"Retrying Job {row['JobID']}..."):
                asyncio.run(retry_job(row["JobID"]))
            st.success(f"Job {row['JobID']} marked for retry.")
    st.write("</div>", unsafe_allow_html=True)

# -----------------------
# Auto Refresh every 60 seconds
# -----------------------
if 'last_refresh' not in st.session_state:
    st.session_state['last_refresh'] = time.time()
else:
    if time.time() - st.session_state['last_refresh'] > 60:
        st.session_state['last_refresh'] = time.time()
        st.experimental_rerun()
