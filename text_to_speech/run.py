from scripts.discovery_utils import (
    get_env_var,
    get_service_endpoint_from_discovery,
    start_grpc_server_with_discovery
)
import logging
from scripts.logging_config import setup_logging
from concurrent import futures
import os
os.environ["GRPC_VERBOSITY"] = "ERROR"
import grpc
from proto import data_pb2, data_pb2_grpc
# from module_c.dummy_text_to_speech import TextToAudio
from text_to_speech.text_to_speech import TextToAudio
# from text_to_speech.text_to_speech_coqui import TextToAudio

# Service configuration
setup_logging()
logger = logging.getLogger("Module C")
SERVICE_NAME = "module_c"
MODULE_C_HOST = get_env_var("MODULE_C_HOST", "0.0.0.0:50053")
MODULE_D_HOST = get_env_var("MODULE_D_HOST") or get_service_endpoint_from_discovery("module_d")

class ModuleCServicer(data_pb2_grpc.ModuleCServicer):
    def __init__(self):
        self._d_channel = grpc.insecure_channel(MODULE_D_HOST)
        self._d_stub = data_pb2_grpc.ModuleDStub(self._d_channel)
        logger.info(f"✅ Initialized connection to Module D at {MODULE_D_HOST}")

        # processing component
        self.TextToAudio = TextToAudio()
        self._audio_counter = 0          # new

    def TextToSpeech(self, request: data_pb2.Comment, context):  # noqa: N802
        logging.info(f"📥 Received text to process (id={request.id})")
        audio_bytes = self.TextToAudio.process(request)
        # assign monotonic integer so Module D never needs to remap
        audio_id = str(self._audio_counter)
        self._audio_counter += 1
        logging.info(f"➡️  Forwarding audio to Module D … (audio_id={audio_id})")        
        try:
            response_d = self._d_stub.PlayAudio(
                data_pb2.Audio(id=audio_id, audio_data=audio_bytes)
            )
            success = response_d.success
            msg = response_d.message
        except grpc.RpcError as exc:
            success = False
            msg = f"❌ Failed to forward audio to Module D: {exc.details()}"
            logging.error(msg)
        return data_pb2.BasicResponse(id=request.id, success=success, message=msg)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    data_pb2_grpc.add_ModuleCServicer_to_server(ModuleCServicer(), server)
    
    # Start server with discovery registration and graceful shutdown
    start_grpc_server_with_discovery(
        server=server,
        service_name=SERVICE_NAME,
        host_address=MODULE_C_HOST,
        metadata={
            "version": "1.0.0",
            "type": "text_to_speech",
            "description": "Converts text to audio"
        }
    )


if __name__ == "__main__":
    serve() 
    