
---

## 🧩 Components and Responsibilities

| Component | Description | Managed By |
|------------|--------------|-------------|
| **Streamlit Dashboard** | User interface built in Python for viewing, filtering, and retrying jobs. | Y/Z |
| **SQL Server** | Central database storing all job metadata, parameters, and execution states. | Infrastructure / DBA |
| **Execution Engine** | Runs the `jobexecuter.exe` program to trigger PowerAgent jobs. | X |
| **jobexecuter.exe** | Python-based executable responsible for reading jobs from DB and triggering PowerAgent. | X |
| **PowerAgent** | Executes actual jobs or workflows and updates SQL Server upon completion. | X |
| **Azure Key Vault** | Stores secrets and connection strings securely for database access. | Infrastructure |
| **OpenTelemetry** | Used for logging, tracing, and performance monitoring across all layers. | Y/Z |

---

## 🗄️ Database Design

### **Table: Jobs**

| Column | Type | Description |
|---------|------|-------------|
| **Client** | VARCHAR(100) | Client identifier |
| **JobID** | INT (PK) | Unique job identifier |
| **JobName** | VARCHAR(200) | Name of the job |
| **Parameters** | VARCHAR(MAX) | Parameters passed to the job (comma-separated) |
| **Status** | VARCHAR(50) | Current status (Pending, Running, Success, Failed) |
| **Message** | VARCHAR(MAX) | Message or error details |
| **ExecutedDateTime** | DATETIME | Last execution time |
| **RefNum** | VARCHAR(50) | Reference number for correlation |
| **RetryCount** | INT | Number of retries attempted |

---

## 🔄 Data Flow

| Step | Description |
|------|--------------|
| **1️⃣ Dashboard → SQL Server** | User triggers retry or adds new job. The record is inserted or updated in the `Jobs` table. |
| **2️⃣ SQL Server → Execution Engine** | The X-managed Execution Engine reads pending/retry jobs. |
| **3️⃣ Execution Engine → PowerAgent** | The engine triggers PowerAgent to execute the job. |
| **4️⃣ PowerAgent → SQL Server** | PowerAgent updates the job status, message, and execution details in SQL Server. |
| **5️⃣ SQL Server → Dashboard** | Streamlit UI fetches updated job data and refreshes the table view. |

---

## 🔐 Authentication & Security

- **Authentication** is handled using **Azure Identity**.
- Streamlit app and executer use **Managed Identity** or **Service Principal** to access:
  - Azure Key Vault (for connection string retrieval)
  - SQL Server (via Azure AD authentication)
- No credentials are stored in plain text or code.

---

## 📊 Observability with OpenTelemetry

- **Dashboard Telemetry**: Captures user interactions like job retries, job addition, and filtering actions.
- **Executor Telemetry**: Tracks PowerAgent trigger requests, latency, and success/failure spans.
- **Trace Export**: Data is exported via OTLP to **Azure Monitor** or **Application Insights**.

---

## ⚙️ Execution Flow

| Stage | Actor | Description |
|--------|--------|--------------|
| **Initiation** | Streamlit Dashboard | User retries or adds a job. |
| **Execution Request** | Execution Engine | Picks job and triggers PowerAgent. |
| **Job Execution** | PowerAgent | Runs the actual workload. |
| **Status Update** | PowerAgent → SQL | Updates status and execution results. |
| **Monitoring** | Dashboard | Displays real-time job status and details. |

---

## 🧰 Technology Stack

| Layer | Technology |
|--------|-------------|
| **Frontend** | Streamlit (Python) |
| **Backend** | SQL Server |
| **Job Executor** | Python (packaged as jobexecuter.exe) |
| **Authentication** | Azure Identity |
| **Secrets Management** | Azure Key Vault |
| **Logging & Tracing** | OpenTelemetry SDK |
| **Deployment** | Streamlit App (local/VM/Container), SQL hosted in Azure |

---

## 🚀 Deployment Overview

| Component | Deployment Mode |
|------------|------------------|
| **Streamlit App** | Packaged Python app hosted internally or on Azure VM |
| **jobexecuter.exe** | Deployed and run by X Team |
| **SQL Server** | Azure SQL or on-prem SQL Server |
| **Key Vault & AAD** | Managed centrally via Azure |

---

## 👥 Ownership & Operations

| Role | Responsibility |
|-------|----------------|
| **Y/Z Team** | Develops and maintains the Streamlit Dashboard and jobexecuter.exe code. |
| **X Team** | Hosts and operates Execution Engine and PowerAgent system. |
| **Infra/DBA Team** | Manages SQL Server and Azure resources (Key Vault, AAD). |

---

## 🧾 Future Enhancements

- Job scheduling and dependency management.
- Email/Teams notification for job failures.
- Pagination and advanced analytics dashboard.
- Integration with Power BI for reporting.

---

## 🧩 Summary

This Job Dashboard provides a **centralized, secure, and observable** platform to manage and track job executions efficiently.  
It ensures **clear separation of responsibilities** between **Y/Z** (application ownership) and **X** (execution ownership), while maintaining transparency and control through **SQL Server and Streamlit UI**.

---
