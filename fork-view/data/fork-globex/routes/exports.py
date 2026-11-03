@router.get("/exports/csv")
def download_csv(day: date):
    return csv_response(db.shipments.on(day))
