@router.get("/portal/shipments")
def customer_shipments(user: CustomerUser):
    return db.shipments.for_customer(user.customer_id)


@router.post("/portal/shipments/{id}/issue")
def report_issue(id: str, body: Issue, user: CustomerUser):
    return support.open_ticket(id, body, reporter=user)
