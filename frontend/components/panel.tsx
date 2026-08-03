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
        "enterprise-card rounded-xl p-5 md:p-6",
        className,
      )}
    >
      {children}
    </section>
  );
}
