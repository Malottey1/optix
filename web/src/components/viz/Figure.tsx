// Every visual sits in a <figure>: the drawing (role="img" with an aria-label summary), a visible
// caption, and a visually hidden table with the exact numbers, so the shape is never the only way
// to read the data.
import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

export interface SrTable {
  caption: string;
  head: string[];
  rows: (string | number)[][];
}

export function VizFigure({
  id,
  viz,
  caption,
  table,
  children,
  className,
  captionClassName,
}: {
  id?: string;
  /** data-viz name, e.g. "crosshairs" (tests look visuals up by it). */
  viz: string;
  caption?: ReactNode;
  table?: SrTable;
  children: ReactNode;
  className?: string;
  captionClassName?: string;
}) {
  return (
    <figure id={id} data-viz={viz} className={cx("m-0 min-w-0", className)}>
      {children}
      {caption && (
        <figcaption className={cx("mt-2 text-[12px] leading-relaxed text-ink-3", captionClassName)}>{caption}</figcaption>
      )}
      {table && (
        <div className="sr-only">
          <table data-sr-table={viz}>
            <caption>{table.caption}</caption>
            <thead>
              <tr>
                {table.head.map((h) => (
                  <th key={h} scope="col">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) =>
                    j === 0 ? (
                      <th key={j} scope="row">
                        {c}
                      </th>
                    ) : (
                      <td key={j}>{c}</td>
                    ),
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  );
}
