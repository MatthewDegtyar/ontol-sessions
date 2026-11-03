export function IssueForm({ shipmentId }) {
  const report = useReportIssue(shipmentId);
  return <Form onSubmit={report}><TextArea name="details" required /></Form>;
}
