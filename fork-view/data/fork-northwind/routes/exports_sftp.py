@router.post("/exports/sftp/schedule")
def schedule_sftp_export(body: SftpSchedule):
    # The idempotency key stops a retry from sending a second file.
    key = f"{body.client}:{body.day}"
    rows = db.shipments.on(body.day)
    return queue.enqueue(send_sftp, rows, body, idempotency_key=key)
