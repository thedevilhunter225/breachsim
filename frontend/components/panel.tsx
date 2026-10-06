import { ReactNode } from "react";
import clsx from "clsx";

export function Panel({
  children,
  className,
  flush = false,
}: {
  children: ReactNode;
  className?: string;
  flush?: boolean;
}) {
  return (
    <section
      className={clsx(
        "enterprise-card rounded-xl",
        !flush && "p-5 md:p-6",
        className,
      )}
    >
      {children}
    </section>
  );
}
