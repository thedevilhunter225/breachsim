import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { revealForDecision, TrainingSimulator } from "./training-simulator";

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

  it("shows the recorded result instead of the choices when the link was already answered", () => {
    const html = renderToStaticMarkup(
      <TrainingSimulator
        token="synthetic-training-token"
        landing={{
          landing_type: "email",
          campaign_name: "Synthetic example",
          recorded_decision: { event_type: "clicked_report", occurred_at: "2026-10-21T15:00:00Z" },
        }}
      />,
    );

    expect(html).toContain("Good response: you reported it");
    expect(html).not.toContain("I would provide details");
    expect(html).toContain("/employee-portal#t=synthetic-training-token");
  });

  it("maps recorded answers to their result", () => {
    expect(revealForDecision("submitted_form_boolean")).toBe("submit");
    expect(revealForDecision("marked_spam")).toBe("report");
    expect(revealForDecision("verified_out_of_band")).toBe("verify");
    expect(revealForDecision(undefined)).toBe("none");
  });
});
