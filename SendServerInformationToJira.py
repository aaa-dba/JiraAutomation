# ============================
# Should be tested before prod
# Run at your own risk.
# ============================

import pyodbc
import requests
from requests.auth import HTTPBasicAuth
import json

# ============================
# Configuration (edit here)
# ============================
DEBUG = True          # When True, do not post to Jira; print what would be sent
POST_TO_JIRA = True    # Set to False to prevent posting even when not debugging

# Safety: if DEBUG is True, force POST_TO_JIRA to False
if DEBUG and POST_TO_JIRA:
    POST_TO_JIRA = False
    print("DEBUG is True; skipping Jira POST and printing payload preview.")

# ----------------------------
# SQL Server connection setup
# ----------------------------
server = "PUT SERVER HERE"
database = "msdb"
username = "PUT USER HERE"
password = "PUT PASSWORD HERE"

# ----------------------------
# Jira API setup
# ----------------------------
# Jira configuration
jira_email = "PUT JIRA EMAIL AUTH HERE"
jira_token = "PUT JIRA API TOKEN HERE"
jira_project_key = "PUT PROJECT KEY HERE"
jira_issue_type_id = "PUT ISSUE TYPE HERE"  # Failed SQL Jobs issue type ID
jira_domain = "PUT COMPANY JIRA DOMAIN HERE"  # Set just the domain here normally like companyname.atlassian.net

# ----------------------------
# Connect to SQL Server
# ----------------------------

jira_url = f"https://{jira_domain}/rest/api/3/issue"
auth = HTTPBasicAuth(jira_email, jira_token)
headers = {"Accept": "application/json", "Content-Type": "application/json"}

conn = pyodbc.connect(
    f'DRIVER={{ODBC Driver 18 for SQL Server}};'
    f'SERVER={server};DATABASE={database};UID={username};PWD={password};'
    f'Encrypt=yes;TrustServerCertificate=yes;'
)
cursor = conn.cursor()

# ----------------------------
# Query SQL Server Information
# ----------------------------
query = """
        SELECT
            SERVERPROPERTY('MachineName') AS MachineName,
            SERVERPROPERTY('ServerName') AS ServerName,
            SERVERPROPERTY('Edition') AS Edition,
            SERVERPROPERTY('ProductVersion') AS ProductVersion,
            cpu_count AS CPU_Count,
            (physical_memory_kb / 1024 / 1024.0) AS Memory_GB,
            (SELECT COUNT(*) FROM sys.databases) AS DatabaseCount,
            (SELECT SUM(size) * 8.0 / 1024 / 1024 FROM sys.master_files) AS TotalDatabaseSize_GB
        FROM sys.dm_os_sys_info; \
        """

cursor.execute(query)
row = cursor.fetchone()

if not row:
    print("No data returned from SQL Server.")
    exit()

columns = [column[0] for column in cursor.description]
data = dict(zip(columns, row))

cursor.close()
conn.close()

# ----------------------------
# Format description for Jira
# ----------------------------
description_lines = [f"{key}: {value}" for key, value in data.items()]
description_text = "\n".join(description_lines)

payload = {
    "fields": {
        "project": {"key": jira_project_key},
        "summary": f"SQL Server Capacity Snapshot - {data.get('ServerName', 'Unknown')}",
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description_text}]
                }
            ]
        },
        "issuetype": {"id": jira_issue_type_id}
    }
}
# ----------------------------
# Create Jira Issue
# ----------------------------
if not POST_TO_JIRA or DEBUG:
    # Dry run: show what would be sent
    summary = payload["fields"]["summary"]
    desc_text = "\n".join(description_lines)[:800]
    print("[DRY RUN] Would create Jira issue with:")
    print(f"  Summary: {summary}")
    print("  Description preview:\n" + desc_text)
else:
    response = requests.post(jira_url, headers=headers, auth=auth, data=json.dumps(payload))
    if response.status_code == 201:
        data_json = {}
        try:
            data_json = response.json()
        except ValueError:
            pass
        issue_key = data_json.get("key") or data_json.get("id", "Unknown")
        print(f"Jira issue created successfully: {issue_key}")
        base_url = jira_url.split('/rest/api')[0]
        print(f"Browse: {base_url}/browse/{issue_key}")
    else:
        print(f"Failed to create Jira issue: {response.status_code}")
        print(response.text)
