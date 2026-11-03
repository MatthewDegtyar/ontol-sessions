import { PairView } from "../../components/pair";

export const metadata = { title: "Comparison · ProductOlogy" };

export default async function Page({ params }) {
  const { id } = await params;
  return <PairView id={id} />;
}
