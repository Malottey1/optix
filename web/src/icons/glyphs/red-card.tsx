// red-card: drawn by hand from the Optix icon sheet. 24 x 24, stroke from <Icon>; see docs/icons.md.
export function RedCardIcon() {
  return (
    <>
      <rect
        x="7"
        y="4"
        width="10"
        height="15"
        rx="1.5"
        transform="rotate(-16 12 11.5)"
        fill="var(--card-red)"
        stroke="var(--card-red)"
      />
    </>
  );
}
