@router.get("/invoices")
def list_invoices():
    return db.invoices.all()


@router.post("/invoices/{id}/send")
def send_invoice(id: str):
    invoice = db.invoices.get(id)
    mailer.send(invoice.contact, render_pdf(invoice))
    return {"sent": True}
