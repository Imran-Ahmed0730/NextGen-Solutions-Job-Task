export function StatusSwitch({
  name,
  label,
  defaultChecked,
}: {
  name: string;
  label: string;
  defaultChecked: boolean;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-3">
      <input
        className="peer sr-only"
        type="checkbox"
        name={name}
        value="on"
        defaultChecked={defaultChecked}
        role="switch"
        aria-label={label}
      />
      <span
        aria-hidden="true"
        className="relative h-6 w-11 rounded-full bg-slate-300 transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:bg-emerald-700 peer-checked:after:translate-x-5 peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-emerald-600 peer-focus-visible:ring-offset-2"
      />
      <span className="text-sm font-medium text-slate-700">{label}</span>
    </label>
  );
}
