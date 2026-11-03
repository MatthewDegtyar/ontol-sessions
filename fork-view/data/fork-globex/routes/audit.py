RETENTION_DAYS = 365


@router.get("/audit")
def audit_log(since: date):
    return db.audit.since(max(since, today() - days(RETENTION_DAYS)))
