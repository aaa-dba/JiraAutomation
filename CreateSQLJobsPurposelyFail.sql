 /*
================================================================================
 Script: CreateSQLJObsPurposelyFail.sql
 Purpose:
   - Creates N SQL Agent demo jobs that always fail (for testing/alerting).
   - Starts those jobs to generate failure history records in msdb.
   - Queries msdb to show the most recent failed outcomes (simple view).

 Usage:
   - Run in a context that has permissions to manage SQL Agent jobs (msdb).
   - Ensure SQL Server Agent service is running to execute the jobs (Step 2).

 Notes:
   - Jobs raise a T-SQL error intentionally via RAISERROR with severity 16.
   - Job names are randomized to avoid collisions; existing matching jobs
     are deleted during creation in case of partial runs.
   - The final query shows: server_name, job_name, category, failed_on,
     failure_reason, retries_attempted, next_run.
================================================================================
*/

USE msdb;
GO

-- 1) Create a few local demo jobs that always fail
--    Adjust @n to control how many demo jobs to create
DECLARE @n int = 3, @i int = 1;

WHILE @i <= @n
BEGIN
    -- Generate unique job/step names to avoid name collisions
    DECLARE @job_id uniqueidentifier = NULL,
            @job_name sysname = N'Demo_Job_' + REPLACE(CONVERT(varchar(36), NEWID()), '-', ''),
            @step_name sysname = N'AlwaysFail_' + RIGHT(CONVERT(varchar(36), NEWID()), 8);

    -- Defensive: if a job with same name exists, remove it first
    IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = @job_name)
        EXEC msdb.dbo.sp_delete_job @job_name = @job_name, @delete_unused_schedule = 1;

    BEGIN TRY
        -- Create the job shell
        EXEC msdb.dbo.sp_add_job
            @job_name = @job_name,
            @enabled = 1,
            @description = N'Intentional fail demo',
            @job_id = @job_id OUTPUT;

        -- Add a single failing step (raise error at severity 16)
        EXEC msdb.dbo.sp_add_jobstep
            @job_id = @job_id,
            @step_name = @step_name,
            @subsystem = N'TSQL',
            @command = N'RAISERROR (''Intentional failure for testing'', 16, 1) WITH LOG;',
            @database_name = N'master',
            @on_success_action = 1,  -- Quit with success (not used, but explicit)
            @on_fail_action = 2;     -- Quit with failure when step errors

        -- Set first step as start step
        EXEC msdb.dbo.sp_update_job @job_id = @job_id, @start_step_id = 1;

        -- Assign to local server (association persists even if Agent is stopped)
        EXEC msdb.dbo.sp_add_jobserver @job_id = @job_id, @server_name = @@SERVERNAME;

        PRINT CONCAT('Created job: ', @job_name);
    END TRY
    BEGIN CATCH
        -- Cleanup on failure to create
        PRINT CONCAT('Create failed for ', @job_name, ' - ', ERROR_MESSAGE());
        IF @job_id IS NOT NULL
            EXEC msdb.dbo.sp_delete_job @job_id = @job_id, @delete_unused_schedule = 1;
    END CATCH;

    SET @i += 1;
END
GO

-- 2) Start the jobs (requires SQL Server Agent service running)
DECLARE @prefix sysname = N'Demo_Job_';
DECLARE @job_name sysname;

-- Enumerate created jobs by prefix; FAST_FORWARD for simple forward-only read
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
SELECT name
FROM msdb.dbo.sysjobs
WHERE name LIKE @prefix + N'%';

OPEN c;
FETCH NEXT FROM c INTO @job_name;
WHILE @@FETCH_STATUS = 0
BEGIN
    BEGIN TRY
        EXEC msdb.dbo.sp_start_job @job_name = @job_name;
        PRINT CONCAT('Started: ', @job_name);
    END TRY
    BEGIN CATCH
        PRINT CONCAT('Start failed: ', @job_name, ' - ', ERROR_MESSAGE());
    END CATCH;

FETCH NEXT FROM c INTO @job_name;
END
CLOSE c; DEALLOCATE c;

-- Wait a few seconds for runs to complete and write history
WAITFOR DELAY '00:00:05';

-- 3) Query failed outcomes for these demo jobs (simple view of latest failed summary rows)
SELECT
    @@SERVERNAME AS server_name,
    j.name       AS job_name,
    c.name       AS category,
    msdb.dbo.agent_datetime(h.run_date, h.run_time) AS failed_on,
    h.message    AS failure_reason,          -- summary message (often includes failing step)
    h.retries_attempted AS retries_attempted,
    msdb.dbo.agent_datetime(jsch.next_run_date, jsch.next_run_time) AS next_run
FROM msdb.dbo.sysjobhistory AS h
         JOIN msdb.dbo.sysjobs AS j
              ON j.job_id = h.job_id
         LEFT JOIN msdb.dbo.syscategories AS c
                   ON c.category_id = j.category_id
         LEFT JOIN msdb.dbo.sysjobschedules AS jsch
                   ON j.job_id = jsch.job_id
WHERE h.step_id = 0              -- job summary row
  AND h.run_status = 0           -- failed
ORDER BY h.instance_id DESC;     -- latest failures first
GO
