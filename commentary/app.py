import grpc
from concurrent import futures
import time
import uuid

# Import generated gRPC files
# These will be generated from .proto files
# For now, we assume they will exist in a 'generated' subdirectory or similar
# e.g., from generated import game_event_pb2, game_event_pb2_grpc
# e.g., from generated import commentary_to_tts_pb2, commentary_to_tts_pb2_grpc

# Placeholder for actual imports until protos are compiled
class Placeholder_GameEventServicer:
    def SendGameEvent(self, request, context):
        print(f"Commentary Service: Received event: {request.event_type} for match {request.match_id}")
        print(f"Details: {request.details}")

        # Dummy commentary logic
        commentary_text = f"This is a dummy commentary for event: {request.event_type}."
        if request.event_type == "goal":
            commentary_text = f"GOOOOAAAL! What a strike for match {request.match_id}!"
        elif request.event_type == "foul":
            commentary_text = f"Ouch, that looked like a nasty foul during match {request.match_id}."

        # Call TTS service
        try:
            # tts_channel = grpc.insecure_channel('tts:50052') # Docker service name and port
            # tts_stub = commentary_to_tts_pb2_grpc.CommentaryToTtsStub(tts_channel)
            # tts_request_id = str(uuid.uuid4())
            # print(f"Commentary Service: Sending to TTS (Req ID: {tts_request_id}): '{commentary_text}'")
            # tts_response = tts_stub.SynthesizeSpeech(
            #     commentary_to_tts_pb2.TextToSpeechRequest(
            #         text=commentary_text,
            #         language_code="en-US",
            #         request_id=tts_request_id
            #     )
            # )
            # print(f"Commentary Service: Received from TTS (Req ID: {tts_response.request_id}): {tts_response.status}, Audio format: {tts_response.audio_format}, Audio length: {len(tts_response.audio_content)} bytes")
            # For now, we'll just print, assuming direct audio return
            # In a real scenario, you'd handle the audio_content (e.g., forward it, store it)
            print(f"Commentary Service: Placeholder for TTS call for text: '{commentary_text}'")

        except grpc.RpcError as e:
            print(f"Commentary Service: Could not connect to TTS service: {e.code()} - {e.details()}")
            # Fallback or error handling
            pass # Placeholder: 실제로는 에러 처리가 필요합니다.

        # return game_event_pb2.EventConfirmation(status="RECEIVED_BY_COMMENTARY", message_id=request.match_id + "_" + str(request.timestamp))
        # Placeholder return
        # For a real EventConfirmation, you'd need the compiled protos.
        # For now, we'll use a dictionary to represent the response.
        class DummyConfirmation:
            def __init__(self, status, message_id):
                self.status = status
                self.message_id = message_id
        return DummyConfirmation(status="RECEIVED_BY_COMMENTARY_DUMMY", message_id=request.match_id + "_" + str(request.timestamp))


def serve_commentary():
    # server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # game_event_pb2_grpc.add_GameToCommentaryServicer_to_server(Placeholder_GameEventServicer(), server)
    # server.add_insecure_port('[::]:50051')
    # print("Commentary Service listening on port 50051...")
    # server.start()
    # server.wait_for_termination()
    # Placeholder server for now until protos are compiled
    print("Commentary Service: Placeholder serve function. Run 'generate_protos.sh' first.")
    print("Then uncomment the gRPC server code and imports.")
    # This part is just to keep the container running for the dummy setup
    print("Starting dummy commentary server loop (does nothing without gRPC setup)...")
    try:
        while True:
            time.sleep(60)
            print("Commentary service still alive...")
    except KeyboardInterrupt:
        print("Commentary service stopping.")

if __name__ == '__main__':
    serve_commentary() 