import { STATUS_LABEL, type Status } from "@/lib/site";

export default function Chip({ s, children }: { s: Status; children?: React.ReactNode }) {
  return (
    <span className="chip" data-s={s}>
      <i aria-hidden />
      {children ?? STATUS_LABEL[s]}
    </span>
  );
}
