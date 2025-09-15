$sw = [System.Diagnostics.Stopwatch]::StartNew();

python evaluate_models.py

$sw.Stop(); 

Write-Host "Execution time: $($sw.Elapsed.ToString())"