export function SendDialog({ invoice, onSend }) {
  return (
    <Dialog title={`Send invoice ${invoice.number}`}>
      <Button onClick={() => onSend(invoice.id)}>Send</Button>
    </Dialog>
  );
}
