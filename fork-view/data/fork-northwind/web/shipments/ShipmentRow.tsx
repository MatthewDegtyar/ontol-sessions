export function ShipmentRow({ shipment }) {
  return (
    <tr>
      <td>{shipment.reference}</td>
      <td><Status value={shipment.status} /></td>
      <td><HoldButton shipment={shipment} /></td>
    </tr>
  );
}
