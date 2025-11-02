/* ================================================================================
  Script to create the 'JIRAUSER' login and grant necessary permissions
  for the automation blog post.
================================================================================
*/
-- Variables (edit these)
DECLARE @LoginName sysname = N'PUT JIRA SQL USER HERE';            -- Desired SQL login/user name
DECLARE @LoginPassword nvarchar(256) = N'PUT YOUR PASSWORD HERE';  -- Strong password

-- Work in master for server-level principal (login)
USE [master];

-- Create the login if it does not exist
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = @LoginName)
    EXEC(
        N'CREATE LOGIN [' + REPLACE(@LoginName, ']', ']]') + N'] ' +
        N'WITH PASSWORD = N''' + REPLACE(@LoginPassword, '''', '''''') + N''', ' +
        N'CHECK_EXPIRATION = OFF, CHECK_POLICY = OFF;'
    );

-- Grant minimal server-level visibility (adjust/remove as needed)
EXEC(N'GRANT VIEW SERVER STATE TO [' + REPLACE(@LoginName, ']', ']]') + N'];');
EXEC(N'GRANT VIEW ANY DEFINITION TO [' + REPLACE(@LoginName, ']', ']]') + N'];');

-- Switch to msdb for database-level principal (user)
USE [msdb];

-- Create the database user if it does not exist
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @LoginName)
    EXEC(
        N'CREATE USER [' + REPLACE(@LoginName, ']', ']]') + N'] ' +
        N'FOR LOGIN [' + REPLACE(@LoginName, ']', ']]') + N'];'
    );

-- Add the user to db_datareader (read-only access to msdb tables)
EXEC(
    N'ALTER ROLE [db_datareader] ADD MEMBER [' + REPLACE(@LoginName, ']', ']]') + N'];'
);
