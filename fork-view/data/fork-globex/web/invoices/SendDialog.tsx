export function SendDialog({ invoice, onSend }) {
  const [po, setPo] = useState(invoice.po_number ?? "");
  return (
    <Dialog title={`Send invoice ${invoice.number}`}>
      <TextField label="PO number" value={po} onChange={setPo} required />
      <Button disabled={!po} onClick={() => onSend(invoice.id, po)}>Send</Button>
    </Dialog>
  );
}
