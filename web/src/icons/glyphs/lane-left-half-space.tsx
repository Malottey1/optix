// lane-left-half-space: drawn by hand from the Optix icon sheet. 24 x 24, stroke from <Icon>; see docs/icons.md.
export function LaneLeftHalfSpaceIcon() {
  return (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="1.2" />
      <rect
        data-lane-band="1"
        x="4"
        y="8.25"
        width="16"
        height="1.9"
        rx=".6"
        fill="var(--lane-fill)"
        fillOpacity="0.7"
        stroke="var(--lane-fill)"
      />
    </>
  );
}
