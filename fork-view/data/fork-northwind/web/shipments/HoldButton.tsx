export function HoldButton({ shipment }) {
  const hold = useHold(shipment.id);
  return <Button onClick={() => hold.ask()}>Hold for customs</Button>;
}
