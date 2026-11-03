def retention_days(client):
    return settings.retention_override(client) or 365


@router.get("/audit")
def audit_log(since: date, client: str):
    return db.audit.since(max(since, today() - days(retention_days(client))))
