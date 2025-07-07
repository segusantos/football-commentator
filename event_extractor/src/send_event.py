import logging
from functools import partial
from typing import Dict, Optional
import grpc
from utils.discovery_utils import get_env_var, get_service_endpoint_from_discovery
from proto import data_pb2, data_pb2_grpc

logging.basicConfig(level=logging.INFO, format="[Module A] %(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S,%f"[:-3])
logger = logging.getLogger(__name__)
MODULE_B_HOST = get_env_var("MODULE_B_HOST") or get_service_endpoint_from_discovery("module_b")

class EventSender:
    """Client wrapper responsible for sending events to Module B asynchronously."""

    def __init__(self):

        self.host = MODULE_B_HOST
        self._channel = grpc.insecure_channel(self.host)
        self._stub = data_pb2_grpc.ModuleBStub(self._channel)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def send_async(self, event_id: str, payload: str) -> None:
        """Fire-and-forget send; returns immediately."""
        event_msg = data_pb2.Event(id=event_id, data=payload)
        future = self._stub.ProcessEvent.future(event_msg)
        future.add_done_callback(partial(self._on_response, event_id=event_id))

    def close(self) -> None:
        self._channel.close()

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _on_response(future: grpc.Future, event_id: str):
        try:
            response = future.result()
            status_icon = "✅" if response.success else "❌"
            logger.info(
                "%s Async response (id=%s): msg='%s'",
                status_icon,
                response.id,
                response.message,
            )
        except grpc.RpcError as exc:
            logger.error("❌ Async call for id=%s failed: %s", event_id, exc)
