@router.post("/exports/s3/schedule")
def schedule_s3_export(body: S3Schedule):
    rows = db.shipments.on(body.day)
    return scheduler.nightly(upload_s3, rows, body)
