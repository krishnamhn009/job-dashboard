# Sample Job Dashboard

A **Streamlit-based Job Dashboard** to manage jobs with features like:

* Add new jobs with parameters
* Retry jobs via icon button
* Filter jobs by Client Name and Status
* Sort jobs by Executed Datetime, Client Name, Job ID, or Retry Count
* Responsive table with horizontal scroll for small screens

---

## 📦 Installation

### 1. Clone this repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 2. Create Python Virtual Environment (optional but recommended)

```bash
python -m venv venv
# Activate venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> This will install `streamlit` and `pandas` required for the dashboard.

---

## 🚀 Run the Dashboard

```bash
streamlit run job_dashboard.py
```

Open your browser at: [http://localhost:8501](http://localhost:8501)

---

## 🛠 Features

* **Add Job:** Add new job with Client Name, Job ID, Job Name, and Parameters (comma-separated). Status defaults to `Pending`.
* **Retry Job:** Retry icon button in the last column increments retry count and updates status to `Retried`.
* **Filter:** By Client Name and Status.
* **Sort:** By Executed Datetime, Client Name, Job ID, Retry Count.
* **Responsive Table:** Table adjusts to screen size; horizontal scroll appears if columns exceed screen width.

---

## 📁 Project Structure

```
job_dashboard/
│
├─ job_dashboard.py      # Main Streamlit app
├─ requirements.txt      # Python dependencies
└─ README.md             # Project documentation
```

---

## 💡 Notes

* The job list is **stored in memory**, so it resets when you restart Streamlit. You can extend it with **CSV or database persistence**.
* Retry button updates the **Retry Count**, **Message**, and **Status** of the job.
* Parameters are displayed as a **single c
