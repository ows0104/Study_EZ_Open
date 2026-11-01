# Dot-source only. Cloud calls execute only when the function is invoked.
function Enable-StudyEZRevision {
  [CmdletBinding()]
  param([Parameter(Mandatory)][string]$Service,
        [Parameter(Mandatory)][string]$Project,
        [Parameter(Mandatory)][string]$Region,
        [Parameter(Mandatory)][string]$ExpectedRevision)
  if ($ExpectedRevision -notmatch ('^' + [regex]::Escape($Service) + '-release-[0-9]+$')) {
    throw 'Expected revision must identify this release attempt.'
  }
  $revisionJson = gcloud run revisions describe $ExpectedRevision --project $Project --region $Region --format='json(metadata.name,status.conditions)'
  if ($LASTEXITCODE -ne 0) { throw 'New revision lookup failed.' }
  $revision = $revisionJson | ConvertFrom-Json -ErrorAction Stop
  $containers = @($revision.status.conditions | Where-Object { $_.type -eq 'ContainerReady' -and $_.status -eq 'True' })
  $ready = @($revision.status.conditions | Where-Object { $_.type -eq 'Ready' -and $_.status -eq 'True' })
  if ($revision.metadata.name -ne $ExpectedRevision -or $containers.Count -ne 1 -or $ready.Count -ne 1) {
    throw 'Expected new revision is not ready.'
  }
  $beforeJson = gcloud run services describe $Service --project $Project --region $Region --format='json(status.latestCreatedRevisionName)'
  if ($LASTEXITCODE -ne 0) { throw 'Service revision lookup failed.' }
  $before = $beforeJson | ConvertFrom-Json -ErrorAction Stop
  if ($before.status.latestCreatedRevisionName -ne $ExpectedRevision) { throw 'Another revision was created; refusing traffic change.' }
  gcloud run services update-traffic $Service --project $Project --region $Region --to-revisions "$ExpectedRevision=100" --quiet | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'New revision traffic switch failed.' }
  $liveJson = gcloud run services describe $Service --project $Project --region $Region --format='json(status.latestCreatedRevisionName,status.latestReadyRevisionName,status.traffic)'
  if ($LASTEXITCODE -ne 0) { throw 'Final traffic lookup failed.' }
  $live = $liveJson | ConvertFrom-Json -ErrorAction Stop
  $positiveTraffic = @($live.status.traffic | Where-Object { $_.percent -gt 0 })
  if ($live.status.latestCreatedRevisionName -ne $ExpectedRevision -or
      $live.status.latestReadyRevisionName -ne $ExpectedRevision -or
      $positiveTraffic.Count -ne 1 -or $positiveTraffic[0].revisionName -ne $ExpectedRevision -or
      $positiveTraffic[0].percent -ne 100) {
    throw 'Expected new revision does not have verified 100 percent traffic.'
  }
  return $ExpectedRevision
}
