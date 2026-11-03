def upload_s3(rows, schedule):
    body = to_csv(rows)
    s3_client(schedule.role_arn).put_object(
        Bucket=schedule.bucket, Key=f"shipments/{schedule.day}.csv", Body=body
    )
