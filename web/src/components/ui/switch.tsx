import * as S from "@radix-ui/react-switch";

export function Switch({
  id,
  label,
  hint,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <label htmlFor={id} className="min-w-0 cursor-pointer">
        <span className="block text-[14px] text-ink">{label}</span>
        {hint && <span className="mt-0.5 block text-[12px] text-ink-3">{hint}</span>}
      </label>
      <S.Root
        id={id}
        checked={checked}
        onCheckedChange={onChange}
        className="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-line-strong bg-surface-3 transition-colors data-[state=checked]:border-accent data-[state=checked]:bg-accent/85"
      >
        <S.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-ink shadow transition-transform data-[state=checked]:translate-x-[22px]" />
      </S.Root>
    </div>
  );
}
