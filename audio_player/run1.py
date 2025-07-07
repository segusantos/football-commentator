import logging
from concurrent.futures import ThreadPoolExecutor
import os
os.environ["GRPC_VERBOSITY"] = "ERROR"
import grpc
from utils.discovery_utils import (
    get_env_var,
    start_grpc_server_with_discovery
)
from utils.logging_config import setup_logging
from proto import data_pb2, data_pb2_grpc
from audio_player.audio_player import OrderedAudioPlayer

# Service configuration
setup_logging()
logger = logging.getLogger("Module D")
SERVICE_NAME = "module_d"
MODULE_D_HOST = get_env_var("MODULE_D_HOST", "0.0.0.0:50054")


class ModuleDServicer(data_pb2_grpc.ModuleDServicer):
    def __init__(self):
        logger.info("🔧 Initializing ModuleDServicer...")
        try:
            self.player = OrderedAudioPlayer()
            logger.info("✅ OrderedAudioPlayer initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize OrderedAudioPlayer: {e}")
            raise

    def PlayAudio(self, request: data_pb2.Audio, context):  # noqa: N802
        try:
            logger.info(f"📥 Received audio request (id={request.id}, data_size={len(request.audio_data)} bytes)")
            logger.info(f"🔍 Client address: {context.peer()}")
            
            self.player.process(request.id, request.audio_data)
            logger.info(f"✅ Enqueued audio (id={request.id}) for playback")
            
            response = data_pb2.BasicResponse(id=request.id, success=True, message="Audio scheduled")
            logger.info(f"📤 Sending success response for id={request.id}")
            return response
            
        except Exception as e:
            error_msg = f"Error processing audio request (id={request.id}): {e}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full exception details:")
            
            return data_pb2.BasicResponse(
                id=request.id, 
                success=False, 
                message=f"Failed to process audio: {e}"
            )


def serve():
    logger.info("🚀 Starting Module D gRPC server...")
    
    try:
        server = grpc.server(ThreadPoolExecutor(max_workers=10))
        logger.info("✅ gRPC server instance created")
        
        servicer = ModuleDServicer()
        data_pb2_grpc.add_ModuleDServicer_to_server(servicer, server)
        logger.info("✅ ModuleDServicer added to server")
        
        # Start server with discovery registration and graceful shutdown
        start_grpc_server_with_discovery(
            server=server,
            service_name=SERVICE_NAME,
            host_address=MODULE_D_HOST,
            metadata={
                "version": "1.0.0",
                "type": "audio_player",
                "description": "Plays audio streams"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        logger.exception("Full exception details:")
        raise


if __name__ == "__main__":
    try:
        serve()
    except KeyboardInterrupt:
        logger.info("🛑 Server interrupted by user")
    except Exception as e:
        logger.error(f"❌ Server failed: {e}")
        import sys
        sys.exit(1)
        