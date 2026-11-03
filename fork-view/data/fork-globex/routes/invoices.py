@router.get("/invoices")
def list_invoices():
    return db.invoices.all()


@router.post("/invoices/{id}/send")
def send_invoice(id: str, po_number: str):
    invoice = db.invoices.get(id)
    invoice.require_po(po_number)
    mailer.send(invoice.contact, render_pdf(invoice))
    return {"sent": True}
