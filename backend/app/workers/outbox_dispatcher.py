from __future__ import annotations

import logging

from app.services.campaign_runs import dispatch_outbox

logger = logging.getLogger("breachsim.outbox_dispatcher")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    total = 0
    # Bound each scheduled execution; another execution will continue from the
    # durable pending rows without creating duplicate Service Bus message IDs.
    for _ in range(20):
        published = dispatch_outbox(limit=100)
        total += published
        if published < 100:
            break
    logger.info("outbox dispatch completed", extra={"published": total})


if __name__ == "__main__":
    main()
