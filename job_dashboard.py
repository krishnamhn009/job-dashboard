import streamlit as st
import pandas as pd
from datetime import datetime

# --- Page Setup ---
st.set_page_config(page_title="Job Dashboard", layout="wide")
st.title("⚙️ Job Dashboard")

# --- CSS for responsive table ---
st.markdown("""
<style>
[data-testid="stDataFrameContainer"] {
    overflow-x: auto;
    width: 100%;
}
[data-testid="stDataFrameContainer"] table {
    font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

# --- Initialize Job Data ---
if "jobs" not in st.session_state:
    st.session_state.jobs = [
        {
            "Client Name": "ABC Corp",
            "Job ID": "J001",
            "Job Name": "Cost Metrics Scan",
            "Message": "Completed Successfully",
            "Status": "Completed",
            "Executed Datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Retry Count": 0,
            "Parameters": "-k eastus, -t 80%"
        },
        {
            "Client Name": "XYZ Ltd",
            "Job ID": "J002",
            "Job Name": "Azure Inventory Fetch",
            "Message": "Failed: Timeout",
            "Status": "Failed",
            "Executed Datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Retry Count": 1,
            "Parameters": "-sub Prod, -timeout 30s"
        }
    ]

# --- Utility Functions ---
def add_job(client, job_id, job_name, params):
    new_job = {
        "Client Name": client,
        "Job ID": job_id,
        "Job Name": job_name,
        "Message": "Pending Execution",
        "Status": "Pending",  # default status
        "Executed Datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Retry Count": 0,
        "Parameters": params
    }
    st.session_state.jobs.append(new_job)

def retry_job(index):
    job = st.session_state.jobs[index]
    job["Retry Count"] += 1
    job["Executed Datetime"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    job["Message"] = f"Retried successfully (Attempt {job['Retry Count']})"
    job["Status"] = "Retried"


# ---------- CONFIG ----------
KEY_VAULT_URL = "https://<your-keyvault>.vault.azure.net/"
SECRET_SERVER = "sql-server-name"
SECRET_DB = "db-name"
SECRET_USER = "username"
SECRET_PWD = "password"

# ---------- CONNECT TO SQL SERVER ----------
db = SQLServerHelper.from_akv(
    key_vault_url=KEY_VAULT_URL,
    secret_name_server=SECRET_SERVER,
    secret_name_db=SECRET_DB,
    secret_name_user=SECRET_USER,
    secret_name_pwd=SECRET_PWD
)
db.connect()

# ---------- FETCH JOBS DATA ----------
def get_jobs_from_db():
    query = "SELECT JobID, ClientName, JobName, Parameters, Message, ExecutedDateTime, RetryCount, Status FROM Jobs"
    try:
        df = db.execute_query(query)
        return df
    except Exception as e:
        st.error(f"Error fetching jobs from DB: {e}")
        return pd.DataFrame(columns=["JobID","ClientName","JobName","Parameters","Message","ExecutedDateTime","RetryCount","Status"])

jobs_df = get_jobs_from_db()

# ---------- STREAMLIT UI ----------
st.title("Job Dashboard")

# Filter section
client_filter = st.text_input("Filter by Client Name")
status_filter = st.selectbox("Filter by Status", options=["All"] + list(jobs_df["Status"].unique()))

filtered_df = jobs_df.copy()

if client_filter:
    filtered_df = filtered_df[filtered_df["ClientName"].str.contains(client_filter, case=False)]

if status_filter != "All":
    filtered_df = filtered_df[filtered_df["Status"] == status_filter]

# Responsive table with horizontal scroll
st.dataframe(filtered_df, use_container_width=True)

# ---------- ADD NEW JOB ----------
st.subheader("Add New Job")
with st.form("add_job_form"):
    client_name = st.text_input("Client Name")
    job_name = st.text_input("Job Name")
    parameters = st.text_input("Parameters (comma-separated)")
    submitted = st.form_submit_button("Add Job")
    if submitted:
        insert_query = "INSERT INTO Jobs (ClientName, JobName, Parameters, Status, RetryCount) VALUES (?, ?, ?, 'Pending', 0)"
        db.execute_non_query(insert_query, params=(client_name, job_name, parameters))
        st.success("Job added successfully!")
        jobs_df = get_jobs_from_db()  # Refresh table

# ---------- RETRY BUTTON ----------
st.subheader("Retry Jobs")
for idx, row in filtered_df.iterrows():
    col1, col2 = st.columns([8, 1])
    col1.write(f"{row['JobID']} - {row['JobName']}")
    if col2.button("🔄", key=f"retry_{row['JobID']}"):
        update_query = "UPDATE Jobs SET RetryCount = RetryCount + 1, Status='Retried' WHERE JobID = ?"
        db.execute_non_query(update_query, params=(row['JobID'],))
        st.success(f"Job {row['JobID']} retried!")
        jobs_df = get_jobs_from_db()  # Refresh table

db.close()

# --- Filter & Sort ---
st.subheader("🔍 Filter & Sort Jobs")
col1, col2, col3 = st.columns(3)
with col1:
    selected_client = st.selectbox(
        "Filter by Client",
        options=["All"] + sorted({j["Client Name"] for j in st.session_state.jobs})
    )
with col2:
    selected_status = st.selectbox(
        "Filter by Status",
        options=["All"] + sorted({j["Status"] for j in st.session_state.jobs})
    )
with col3:
    sort_by = st.selectbox(
        "Sort by", ["Executed Datetime", "Client Name", "Job ID", "Retry Count"]
    )
    sort_order = st.radio("Sort order", ["Descending", "Ascending"], horizontal=True)

# --- Apply Filters ---
jobs_filtered = st.session_state.jobs
if selected_client != "All":
    jobs_filtered = [j for j in jobs_filtered if j["Client Name"] == selected_client]
if selected_status != "All":
    jobs_filtered = [j for j in jobs_filtered if j["Status"] == selected_status]

# --- Convert to DataFrame ---
df = pd.DataFrame(jobs_filtered)
df = df.sort_values(by=sort_by, ascending=(sort_order == "Ascending"))

# --- Display Table with Retry Icon Column ---
st.subheader("📋 Existing Jobs")
if not df.empty:
    # Table headers
    headers = [
        "Client Name", "Job ID", "Job Name", "Message",
        "Parameters", "Status", "Executed Datetime", "Retry Count", "Action"
    ]
    cols_widths = [2, 1, 2, 3, 2, 1, 2, 1, 1]

    # Header row
    header_cols = st.columns(cols_widths)
    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    # Data rows
    for i, row in df.iterrows():
        row_cols = st.columns(cols_widths)
        row_cols[0].write(row["Client Name"])
        row_cols[1].write(row["Job ID"])
        row_cols[2].write(row["Job Name"])
        row_cols[3].write(row["Message"])
        row_cols[4].write(row["Parameters"])
        row_cols[5].write(row["Status"])
        row_cols[6].write(row["Executed Datetime"])
        row_cols[7].write(row["Retry Count"])
        # Retry button in last column
        if row_cols[8].button("🔁", key=f"retry_{i}", help=f"Retry Job {row['Job ID']}"):
            retry_job(i)
            st.experimental_rerun()
else:
    st.info("No jobs available for the selected filter.")

# --- Add New Job Section ---
st.markdown("---")
st.subheader("➕ Add New Job")
with st.form("add_job_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        client_name = st.text_input("Client Name")
    with col2:
        job_id = st.text_input("Job ID")
    with col3:
        job_name = st.text_input("Job Name")

    params = st.text_input(
        "Job Parameters (comma-separated, e.g. `-k eastus, -d prod, -env dev`)"
    )

    submitted = st.form_submit_button("Add Job")
    if submitted:
        if client_name and job_id and job_name:
            add_job(client_name, job_id, job_name, params)
            st.success(f"✅ Job '{job_name}' added successfully!")
            st.experimental_rerun()
        else:
            st.error("⚠️ Please fill in Client, Job ID, and Job Name.")
