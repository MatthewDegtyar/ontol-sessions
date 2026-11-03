def send_sftp(rows, schedule):
    body = to_csv(rows, columns=COLUMNS)
    with sftp_connect(schedule.host, schedule.credential_ref) as conn:
        conn.put(f"shipments-{schedule.day}.csv", body)
