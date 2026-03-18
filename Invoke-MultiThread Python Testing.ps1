param([string]$Action, [string]$JsonData)

function Invoke-MultiThreadTeams {
    param(
        [Parameter(Mandatory=$true)]
        [array]$InputData, # The list of users/UPNs

        [Parameter(Mandatory=$true)]
        [scriptblock]$WorkItem, # The custom logic to run per user

        [int]$Throttle = 6,
        [int]$RetryCount = 3
    )

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $logQueue = [System.Collections.Concurrent.ConcurrentQueue[object]]::new()
    $total = $InputData.Count

    # 1. Use the most reliable default state for PS7
    $iss = [System.Management.Automation.Runspaces.InitialSessionState]::CreateDefault()
    
    # 2. Force Full Language Mode
    $iss.LanguageMode = "FullLanguage"
    
    # 3. Import the modules by name (PowerShell handles the type resolution)
    # We add Microsoft.PowerShell.Core to ensure Get-Command/Get-Date are there
    $iss.ImportPSModule(@("Microsoft.PowerShell.Core", "Microsoft.PowerShell.Utility", "MicrosoftTeams"))

    # 4. Create the pool
    $pool = [RunspaceFactory]::CreateRunspacePool(1, $Throttle, $iss, $Host)
    $pool.Open()

    $jobs = [System.Collections.Generic.List[object]]::new()

    # This is the "Wrapper" that runs inside every Runspace
    $internalWrapper = {
        param($upn, $RetryCount, $logQueue, $ExternalWorkItem)

        # FIX: Re-create the ScriptBlock from the string/object passed in
        # This ensures the 'GetSteppablePipeline' error doesn't occur
        $localWorkItem = [scriptblock]::Create($ExternalWorkItem.ToString())

        # Use the Fully Qualified Name for Get-Date to be 100% safe
        $now = Microsoft.PowerShell.Utility\Get-Date
        
        $logQueue.Enqueue([PSCustomObject]@{
            Timestamp = $now; User = $upn; Level = "INFO"; Message = "Processing started"
        })

        $attempt = 0
        while ($attempt -lt $RetryCount) {
            try {
                $attempt++
                
                # EXECUTE USER SCRIPT BLOCK HERE
                # We pass the $upn to the script block so the user can use it
                $check = &$localWorkItem -upn $upn

                $logQueue.Enqueue([PSCustomObject]@{
                    $now = Microsoft.PowerShell.Utility\Get-Date
                    Timestamp = $now; User = $upn; Level = "INFO"; Message = "User processed successfully"
                })

                return [PSCustomObject]@{
                    User    = $upn
                    Result  = $check # Return whatever the custom script produced
                    Attempt = $attempt
                    Status  = "Success"
                }
            }
            catch {
                if ($attempt -ge $RetryCount) {
                    $logQueue.Enqueue([PSCustomObject]@{
                        Timestamp = Get-Date; User = $upn; Level = "ERROR"; Message = $_.Exception.Message
                    })
                    return [PSCustomObject]@{
                        User = $upn; Status = "Failed"; Attempt = $attempt; Error = $_.Exception.Message
                    }
                }
                Start-Sleep -Seconds (2 * $attempt)
            }
        }
    }

    foreach ($item in $InputData) {
        # Cast explicitly to string to ensure the Runspace handles it correctly
        [string]$upn = $item.UserPrincipalName
        $ps = [powershell]::Create().AddScript($internalWrapper)
        $ps.RunspacePool = $pool
        
        # Pass the custom WorkItem script block as the 4th argument
        [void]$ps.AddArgument($upn).AddArgument($RetryCount).AddArgument($logQueue).AddArgument($WorkItem)

        $jobs.Add([PSCustomObject]@{ Pipe = $ps; Handle = $ps.BeginInvoke() })
    }

    # Result Collection Logic
    $results = [System.Collections.Generic.List[object]]::new()
    $completed = 0

    while ($jobs.Count -gt 0) {
        foreach ($job in $jobs.ToArray()) {
            if ($job.Handle.IsCompleted) {
                $results.Add($job.Pipe.EndInvoke($job.Handle))
                $job.Pipe.Dispose()
                [void]$jobs.Remove($job)
                $completed++
                
                # No write-progress when calling from Streamlit
                # Write-Progress -Activity "Processing Users" -Status "$completed / $total" -PercentComplete (($completed/$total)*100)
            }
        }
    Microsoft.PowerShell.Utility\Start-Sleep -Milliseconds 100
    }

    $pool.Close(); $pool.Dispose()
    
    # Return everything as a combined object
    return [PSCustomObject]@{
        Data = $results
        Logs = $logQueue.ToArray()
        Time = $watch.Elapsed.TotalSeconds
    }
}

if ($Action -eq "Login") {
    try {
        Connect-MicrosoftTeams -ErrorAction Stop
        $firstUser = Get-CsOnlineUser | Select-Object -ExpandProperty UserPrincipalName -First 1
        $tenantDomain = $firstUser.Split('@')[1]
        Write-Host "SUCCESS: Authenticated"
        Write-Host "TENANT_DOMAIN: $tenantDomain"
    } catch { Write-Host "ERROR: $($_.Exception.Message)" }
}
if ($Action -eq "Logout") {
    try {
        Disconnect-MicrosoftTeams -ErrorAction SilentlyContinue
        Write-Host "SUCCESS: Disconnected"
    } catch { Write-Host "ERROR: $($_.Exception.Message)" }
}
if ($Action -eq "Validation") {
    $UserData = $JsonData | ConvertFrom-Json
    Connect-MicrosoftTeams 
    Write-Host "Processing $($UserData.Count) records for validation..."
    $myAction = {
        param($upn) # This comes from the -upn argument in the wrapper

        # If the Runspace fails to 'see' the command, this forces a local re-import 
        # for just this thread. It's a safety net for PS7 Runspaces.
        if (-not (Get-Command Get-CsOnlineUser -ErrorAction SilentlyContinue)) {
            Import-Module MicrosoftTeams -ErrorAction SilentlyContinue
        }

        # Command to issue
        return Get-CsOnlineUser -Identity $upn -ErrorAction Stop
    }

    $process = Invoke-MultiThreadTeams -InputData $UserData -WorkItem $myAction -Throttle 10

    # Pass results back to Python
    # Create a structured result for Python
    $FinalOutput = [PSCustomObject]@{
        Summary = [PSCustomObject]@{
            Total      = $UserData.Count
            Success    = ($process.Data | Where-Object { $_.Status -eq "Success" }).Count
            Failed     = ($process.Data | Where-Object { $_.Status -eq "Failed" }).Count
            Duration   = $process.Time
        }
        # Flatten the results so each row has User, Status, and Error/Result
        Details = $process.Data | ForEach-Object {
            [PSCustomObject]@{
                User    = $_.User
                Status  = $_.Status
                Details = if ($_.Status -eq "Success") { "Validated" } else { $_.Error }
                Attempt = $_.Attempt
            }
        }
    }

    # Final JSON output for Python to capture
    $FinalOutput | ConvertTo-Json -Depth 5 -Compress

}
if ($Action -eq "BulkSync") {
    $UserData = $JsonData | ConvertFrom-Json
    Connect-MicrosoftTeams 
    Write-Host "Processing $($UserData.Count) records..."
}