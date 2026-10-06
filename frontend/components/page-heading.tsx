import type { ReactNode } from "react";

export function PageHeading({ title, description, eyebrow, actions }: {
  title: string;
  description: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="workspace-heading">
      <div>
        {eyebrow ? <p className="workspace-eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        <p className="workspace-description">{description}</p>
      </div>
      {actions ? <div className="workspace-heading-actions">{actions}</div> : null}
    </header>
  );
}
