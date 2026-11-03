import CompareForm from "../components/compare-form";

export const metadata = { title: "Compare repos · ProductOlogy", description: "Compare a GitHub repo with its fork to see what the fork added." };

export default function Demo() {
  return (
    <div className="demo-head">
      <CompareForm />
    </div>
  );
}
