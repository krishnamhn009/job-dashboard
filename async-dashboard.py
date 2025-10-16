# job_dashboard_async_filters.py
import streamlit as st
import pandas as pd
import asyncio
import aioodbc
from azure.identity.aio import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient
from datetime import datetime
from opentelemetry import trace, _logs
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.streamlit import StreamlitInstrumentor

# -----------------------
# OpenTelemetry Initialization
# -----------------------
resource = Resource(attributes={SERVICE_NAME: "JobDashboardAsync"})
tracer_provider = TracerProvider(resource=resource)
span_processor = BatchSpanProcessor(OTLPSpanExporter())
tracer_provider.add_span_processor(span_processor)
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# Logging
logger_provider = LoggerProvider(resource=resource)
log_exporter = OTLPLogExporter()
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
_logs.set_logger_provider(logger_provider)
logger = _logs.get_logger("JobDashboardAsyncLogger", "1.0.0")

# Streamlit Instrumentation
StreamlitInstrumentor().instrument()

# -----------------------
# Streamlit UI
# -----------------------
st.set_page_config(page_title="Job Dashboard Async", layout="wide")

# Title and Refresh
col_title, col_refresh = st.columns([8, 1])
with col_title:
    st.title("📊 Job Execution Dashboard (Async)")
with col_refresh:
    if st.button("🔄 Refresh"):
        st.experimental_rerun()

# -----------------------
# Async SQL Connection
# -----------------------
async def get_sql_connection():
    key_vault_url = st.secrets["keyvault"]["url"]
    secret_name = st.secrets["keyvault"]["sql_secret_name"]
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
    sql_conn_str = await secret_client.get_secret(secret_name)
    conn = await aioodbc.connect(sql_conn_str.value, autocommit=True)
    return conn

# -----------------------
# Fetch Jobs Async
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

# -----------------------
# Add New Job Async
# -----------------------
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

# -----------------------
# Retry Job Async
# -----------------------
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
# Fetch and Display Jobs
# -----------------------
st.subheader("📋 Job Execution Table")
with st.spinner("Loading jobs..."):
    df = asyncio.run(fetch_jobs())

# -----------------------
# Filters
# -----------------------
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
