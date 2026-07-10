import { ReactNode } from "react";
import clsx from "clsx";

export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={clsx(
        "enterprise-card rounded-lg p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}
