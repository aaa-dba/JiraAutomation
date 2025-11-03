/* ================================================================================
  Purpose: Create a SQL login, grant minimal perms, map to msdb user with read access
  How to use: Set @LoginName and @LoginPassword, then run.
================================================================================ */

-- Variables (edit these)
DECLARE @LoginName       sysname        = N'PUT JIRA SQL USER HERE';
DECLARE @LoginPassword   nvarchar(256)  = N'PUT YOUR PASSWORD HERE';

-- Helpers for safe dynamic SQL
DECLARE @LoginQuoted sysname       = QUOTENAME(@LoginName, N']');                 -- [name]
DECLARE @PwdEscaped nvarchar(512)  = REPLACE(@LoginPassword, N'''', N'''''');     -- escape '

/* Step 1: Create login in master (if missing) */
USE [master];

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @LoginName)
BEGIN
    EXEC (N'CREATE LOGIN ' + @LoginQuoted +
          N' WITH PASSWORD = N''' + @PwdEscaped + N''', CHECK_EXPIRATION = OFF, CHECK_POLICY = OFF;');
END

/* Step 2: Grant server-level permissions */
EXEC (N'GRANT VIEW SERVER STATE TO '   + @LoginQuoted + N';');
EXEC (N'GRANT VIEW ANY DEFINITION TO ' + @LoginQuoted + N';');  -- remove if not needed

/* Step 3: Create msdb user mapped to the login (if missing) */
USE [msdb];

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @LoginName)
BEGIN
    EXEC (N'CREATE USER ' + @LoginQuoted + N' FOR LOGIN ' + @LoginQuoted + N';');
END

/* Step 4: Add to db_datareader in msdb */
EXEC (N'ALTER ROLE [db_datareader] ADD MEMBER ' + @LoginQuoted + N';');
