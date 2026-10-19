"""Lecture-scoped slide choices for private question authoring."""
from sqlalchemy import select
from app.models import Asset, SLIDE_KINDS


def choices(db, row, inherited):
    report = (row.validation or {}).get("slideFocus") or {}
    available = {asset.id: {"assetId": asset.id, "page": asset.slide_no, "sourceId": "self",
                          "sourceRunId": row.run_id, "sourceFilename": report.get("sourceFilename", "")}
                 for asset in db.scalars(select(Asset).where(
                     Asset.subject == row.subject, Asset.run_id == row.run_id,
                     Asset.kind == SLIDE_KINDS["bank"], Asset.slide_no > 0).order_by(Asset.slide_no, Asset.id))}
    for reference in inherited:
        available[reference["assetId"]] = reference
    return available
