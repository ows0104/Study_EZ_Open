param([Parameter(Mandatory)][string]$Helper)
$ErrorActionPreference = 'Stop'
. $Helper
$script:scenario = ''
$script:switched = $false
$script:serviceReads = 0
$script:expected = 'studyez-api-release-123'
function global:gcloud {
  $global:LASTEXITCODE = 0
  if ($args[1] -eq 'revisions') {
    if ($script:scenario -eq 'revision_lookup_failed') { $global:LASTEXITCODE = 1; return }
    if ($script:scenario -eq 'malformed') { return 'not-json' }
    $name = if ($script:scenario -eq 'wrong_revision') { 'studyez-api-old' } else { $script:expected }
    $ready = if ($script:scenario -eq 'not_ready') { 'False' } else { 'True' }
    return @{metadata=@{name=$name};status=@{conditions=@(@{type='Ready';status=$ready},@{type='ContainerReady';status='True'})}} | ConvertTo-Json -Depth 5 -Compress
  }
  if ($args[2] -eq 'update-traffic') {
    if ($script:scenario -eq 'switch_failed') { $global:LASTEXITCODE=1; return }
    if ($args -notcontains '--to-revisions' -or $args -notcontains ($script:expected+'=100')) { throw 'Wrong traffic target' }
    $script:switched=$true; return
  }
  $script:serviceReads++
  if ($script:scenario -eq 'service_lookup_failed' -or ($script:scenario -eq 'final_lookup_failed' -and $script:switched)) { $global:LASTEXITCODE=1; return }
  $created = if ($script:scenario -eq 'concurrent') { 'studyez-api-other' } else { $script:expected }
  if (-not $script:switched) { return @{status=@{latestCreatedRevisionName=$created}} | ConvertTo-Json -Depth 4 -Compress }
  $ready = if ($script:scenario -eq 'old_ready') { 'studyez-api-old' } else { $script:expected }
  $target = if ($script:scenario -eq 'old_traffic') { 'studyez-api-old' } else { $script:expected }
  $percent = if ($script:scenario -eq 'partial_traffic') { 50 } else { 100 }
  $traffic = @(@{revisionName=$target;percent=$percent},@{revisionName='studyez-api-tagged';tag='old-tag'})
  return @{status=@{latestCreatedRevisionName=$created;latestReadyRevisionName=$ready;traffic=$traffic}} | ConvertTo-Json -Depth 6 -Compress
}
$cases=@('success','revision_lookup_failed','wrong_revision','not_ready','concurrent','service_lookup_failed','switch_failed','old_ready','old_traffic','partial_traffic','final_lookup_failed','malformed')
foreach ($case in $cases) {
  $script:scenario=$case; $script:switched=$false; $script:serviceReads=0
  $failed=$false
  try { $result=Enable-StudyEZRevision -Service studyez-api -Project fixture -Region fixture -ExpectedRevision $script:expected }
  catch { $failed=$true }
  if ($case -eq 'success') {
    if ($failed -or $result -ne $script:expected -or -not $script:switched) { throw "Success path failed: $case" }
  } elseif (-not $failed) { throw "Accepted unsafe outcome: $case" }
  if ($case -in @('revision_lookup_failed','wrong_revision','not_ready','concurrent','service_lookup_failed','malformed') -and $script:switched) { throw "Changed traffic before validation: $case" }
}
Write-Output ('PASS: '+$cases.Count+' isolated revision/traffic scenarios; no cloud calls')
