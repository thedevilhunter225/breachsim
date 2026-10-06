import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TrainingSimulator } from "./training-simulator";

describe("training landing privacy", () => {
  it("offers behavior choices without accepting credentials or verification codes", () => {
    const html = renderToStaticMarkup(
      <TrainingSimulator
        token="synthetic-training-token"
        landing={{ landing_type: "email", campaign_name: "Synthetic example" }}
      />,
    );

    expect(html).toContain("I would provide details");
    expect(html).toContain("Verify independently");
    expect(html).toContain("Report suspicious");
    expect(html).not.toContain('type="password"');
    expect(html).not.toContain("Verification code");
    expect(html).not.toContain('name="email"');
  });
});
