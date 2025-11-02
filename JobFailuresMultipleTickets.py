# ========================================================
# This grabs all failed jobs & sends a ticket per job. 
# Should be tested before prod
# Run at your own risk.
# ========================================================

import pyodbc
import requests
from requests.auth import HTTPBasicAuth
import json

# ============================
# Configuration (edit here)
# ============================
# Flags
DEBUG = False              # When True, send "this is a test" as summary/description
TEST_SINGLE_ISSUE = True   # When True, only create one Jira ticket

# safety: avoid spamming test issues when in DEBUG mode
if DEBUG and not TEST_SINGLE_ISSUE:
    TEST_SINGLE_ISSUE = True
    print("DEBUG is True; forcing TEST_SINGLE_ISSUE=True to avoid multiple test issues.")

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
    f'SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=yes;'
)

cursor = conn.cursor()

# Query latest failed jobs (simple, single statement)
query = """
        SELECT
          @@SERVERNAME AS server_name,
          j.name       AS job_name,
          c.name       AS category,
          msdb.dbo.agent_datetime(h.run_date, h.run_time) AS failed_on,
          h.message    AS failure_reason,
          h.retries_attempted AS retries_attempted,
          msdb.dbo.agent_datetime(jsch.next_run_date, jsch.next_run_time) AS next_run
        FROM msdb.dbo.sysjobhistory AS h
        JOIN msdb.dbo.sysjobs AS j
          ON j.job_id = h.job_id
        LEFT JOIN msdb.dbo.syscategories AS c
          ON c.category_id = j.category_id
        LEFT JOIN msdb.dbo.sysjobschedules AS jsch
          ON j.job_id = jsch.job_id
        WHERE h.step_id = 0
          AND h.run_status = 0
        ORDER BY h.instance_id DESC;
        """

cursor.execute(query)
failed_jobs = cursor.fetchall()
print(f"Fetched {len(failed_jobs)} failed jobs from SQL Server '{server}' (database '{database}')")
if failed_jobs:
    s = failed_jobs[0]
    # server_name, job_name, category, failed_on, failure_reason, retries_attempted, next_run
    print(
        "Sample row -> "
        f"server={s[0]}, job={s[1]}, category={s[2]}, failed_on={s[3]}, reason={s[4]}, retries={s[5]}, next_run={s[6]}"
    )

# Jira setup is configured at the top of this file

# ----------------------------
# Loop through failed jobs and create Jira issues
# ----------------------------
for job in (failed_jobs[:1] if TEST_SINGLE_ISSUE else failed_jobs):
    (
        server_name,
        job_name,
        category,
        failed_on,
        failure_reason,
        retries_attempted,
        next_run,
    ) = job

    summary = (
        "this is a test"
        if DEBUG
        else f"SQL Job failed: {server_name}"
    )

    if DEBUG:
        description_text = "this is a test"
    else:
        # Build a clear, multiline explanation
        description_text = (
            f"Job '{job_name}' failed on server '{server_name}'.\n"
            f"Category: {category or 'N/A'}\n"
            f"Failed on: {failed_on}\n"
            f"Reason: {failure_reason or 'No message provided'}\n"
            f"Retries attempted: {retries_attempted if retries_attempted is not None else 0}\n"
            f"Next scheduled run: {next_run or 'Not scheduled'}\n"
        )

    payload = {
        "fields": {
            "project": {"key": jira_project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description_text}
                        ]
                    }
                ]
            },
            "issuetype": {"id": jira_issue_type_id}
        }
    }

    response = requests.post(jira_url, headers=headers, auth=auth, data=json.dumps(payload))

    if response.status_code == 201:
        # Try to extract the Jira issue key/id from the response
        issue_key = None
        try:
            data = response.json()
            issue_key = data.get("key") or data.get("id")
        except ValueError:
            pass
        if issue_key:
            print(f"Issue created for {job_name}{' (DEBUG MODE)' if DEBUG else ''}: {issue_key}")
            base_url = jira_url.split('/rest/api')[0]
            print(f"Browse: {base_url}/browse/{issue_key}")
        else:
            print(f"Issue created for {job_name}{' (DEBUG MODE)' if DEBUG else ''} (could not parse issue key)")
    else:
        print(f"Failed to create issue for {job_name}: {response.status_code}")
        print(response.text)
