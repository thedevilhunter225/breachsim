from __future__ import annotations

import json
import logging
import signal

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient

from app.core.config import settings
from app.services.campaign_runs import process_delivery_batch

logger = logging.getLogger("breachsim.service_bus_worker")
running = True


def _stop(*_args) -> None:
    global running
    running = False


def main() -> None:
    if not settings.service_bus_fully_qualified_namespace:
        raise RuntimeError("SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE is required")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    with ServiceBusClient(
        fully_qualified_namespace=settings.service_bus_fully_qualified_namespace,
        credential=credential,
    ) as client:
        with client.get_queue_receiver(
            queue_name=settings.service_bus_campaign_queue,
            max_wait_time=20,
            prefetch_count=10,
        ) as receiver:
            idle_polls = 0
            while running and idle_polls < 3:
                messages = receiver.receive_messages(max_message_count=10, max_wait_time=5)
                if not messages:
                    idle_polls += 1
                    continue
                idle_polls = 0
                for message in messages:
                    try:
                        raw_body = b"".join(message.body).decode("utf-8")
                        payload = json.loads(raw_body)
                        process_delivery_batch(payload["attempt_ids"])
                    except Exception:
                        logger.exception("delivery batch failed", extra={"message_id": message.message_id})
                        receiver.abandon_message(message)
                    else:
                        receiver.complete_message(message)


if __name__ == "__main__":
    main()
