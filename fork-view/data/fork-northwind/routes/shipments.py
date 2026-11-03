@router.get("/shipments")
def list_shipments(status: str | None = None):
    return db.shipments.filter(status=status)


@router.post("/shipments")
def create_shipment(body: NewShipment):
    return db.shipments.create(body)


@router.get("/shipments/{id}/tracking")
def track_shipment(id: str):
    return carriers.latest_events(id)


@router.post("/shipments/{id}/customs-hold")
def hold_for_customs(id: str, body: HoldReason):
    return db.shipments.set_hold(id, body.reason)
