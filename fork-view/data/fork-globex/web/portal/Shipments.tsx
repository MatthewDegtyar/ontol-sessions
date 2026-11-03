export function PortalShipments() {
  const { data } = useSWR("/portal/shipments");
  return <ShipmentList rows={data} />;
}
