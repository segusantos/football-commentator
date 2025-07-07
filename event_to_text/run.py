import logging
from concurrent import futures
import os
os.environ["GRPC_VERBOSITY"] = "ERROR"
import grpc
from utils.discovery_utils import (
    get_env_var, 
    get_service_endpoint_from_discovery, 
    start_grpc_server_with_discovery
)
from proto import data_pb2, data_pb2_grpc
# from module_b.dummy_event_to_text import EventToText
from event_to_text.event_to_text import EventToText

# Service configuration
logging.basicConfig(level=logging.INFO, format="[Module B] %(asctime)s - %(levelname)s - %(message)s")
SERVICE_NAME = "module_b"
MODULE_B_HOST = get_env_var("MODULE_B_HOST", "0.0.0.0:50052")
MODULE_C_HOST = get_env_var("MODULE_C_HOST") or get_service_endpoint_from_discovery("module_c")

class ModuleBServicer(data_pb2_grpc.ModuleBServicer):
    """Receives events from Module A and forwards text to Module C."""

    def __init__(self):
        # Create a single channel to Module C for reuse
        self._c_channel = grpc.insecure_channel(MODULE_C_HOST)
        self._c_stub = data_pb2_grpc.ModuleCStub(self._c_channel)
        logging.info(f"✅ Initialized connection to Module C at {MODULE_C_HOST}")

        # Processing component – heavy NLP, can tune delays
        self.eventToText = EventToText()

    def ProcessEvent(self, request: data_pb2.Event, context):  # noqa: N802 (grpc naming)
        logging.info(f"📥 Received event (id={request.id})")
        text = self.eventToText.process(request)
        if not text:
            msg = f"❌ No text generated for event (id={request.id})"
            return data_pb2.BasicResponse(id=request.id, success=True, message=msg)
        logging.info(f"➡️  Forwarding text (id={request.id}) to Module C")
        try:
            response_c = self._c_stub.TextToSpeech(
                data_pb2.Comment(id=request.id, text=text)
            )
            success = response_c.success
            msg = response_c.message
        except grpc.RpcError as exc:
            success = False
            msg = f"❌ Failed to forward text to Module C: {exc.details()}"
            logging.error(msg)
        return data_pb2.BasicResponse(id=request.id, success=success, message=msg)


def main():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    data_pb2_grpc.add_ModuleBServicer_to_server(ModuleBServicer(), server)
    
    # Start server with discovery registration and graceful shutdown
    start_grpc_server_with_discovery(
        server=server,
        service_name=SERVICE_NAME,
        host_address=MODULE_B_HOST,
        metadata={
            "version": "1.0.0",
            "type": "event_processor",
            "description": "Converts events to text"
        }
    )


if __name__ == "__main__":
    main() 
