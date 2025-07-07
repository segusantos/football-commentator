"""
Discovery integration utilities
Provides functions for service registration and discovery
"""

import signal
from discovery.client import get_service_endpoint, DiscoveryError, register_service, unregister_service
import logging
import socket
from utils.utils import get_env_var
import os
import grpc

logger = logging.getLogger("Discovery Utils")


def start_grpc_server_with_discovery(
    server : grpc.server,
    service_name: str, 
    host_address: str,
    metadata: dict = None
):
    """
    Start a gRPC server with automatic discovery registration and graceful shutdown
    
    Args:
        server: gRPC server instance
        service_name: Name to register the service as
        host: Host address in "host:port" format
        metadata: Optional metadata for the service
    """
    # Add server port
    service_host = host_address.split(":")[0]
    service_port = extract_port_from_host(host_address)
    server.add_insecure_port(f"{service_host}:{service_port}")
    auto_register_service(
        service_name=service_name,
        service_host=service_host,
        service_port=service_port,
        metadata=metadata or {}
    )
    
    # Setup graceful shutdown
    setup_graceful_shutdown(server, service_name)
    
    # Start server
    server.start()
    logger.info(f"📡 {service_name} gRPC server listening on {service_host}:{service_port}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        # Signal handler will take care of cleanup
        logger.info("🔄 Received KeyboardInterrupt, letting signal handler manage shutdown")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        # Cleanup and exit
        try:
            unregister_service(service_name)
        except:
            pass
        os._exit(1) 


def get_service_endpoint_from_discovery(service_name: str) -> str:
    """
    Get service endpoint using discovery service
    
    Args:
        service_name: Name of the service in discovery registry
    
    Returns:
        Service endpoint as "host:port" string
        
    Raises:
        DiscoveryError: If service discovery fails
    """
    endpoint = get_service_endpoint(service_name)
    logger.debug(f"🔍 Found {service_name} via discovery: {endpoint}")
    return endpoint

def auto_register_service(
    service_name: str,
    service_port: int,
    service_host: str = None,
    metadata: dict = None
) -> bool:
    """
    Automatically register this service with the discovery server
    
    Args:
        service_name: Name to register the service as
        service_port: Port the service is running on
        discovery_url: URL of the discovery server
        metadata: Optional metadata to include
    
    Returns:
        True if registration successful, False otherwise
    """
    try:
        service_host = get_local_ip()
        result = register_service(
            service_name=service_name,
            service_host=service_host,  
            service_port=service_port,
            metadata=metadata
        )
        logger.info(f"✅ Registered {service_name} at {service_host}:{service_port} to discovery server at {get_env_var('DISCOVERY_URL', 'http://localhost:8000')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to register {service_name}: {e}")
        return False

def extract_port_from_host(host_string: str, default_port: int = 50051) -> int:
    """
    Extract port number from host:port string
    
    Args:
        host_string: String in format "host:port" or "host"
        default_port: Default port if parsing fails
    
    Returns:
        Port number as integer
    """
    try:
        if ':' in host_string:
            return int(host_string.split(':')[1])
        else:
            return default_port
    except (IndexError, ValueError):
        return default_port

def setup_graceful_shutdown(server, service_name: str = None):
    """
    Setup graceful shutdown handlers for a gRPC server
    
    Args:
        server: gRPC server instance
        service_name: Name of the service for unregistration (optional)
    """
    shutdown_initiated = False
    
    def graceful_shutdown(signum, frame):
        """Handle graceful shutdown"""
        nonlocal shutdown_initiated
        
        # Prevent multiple shutdown attempts
        if shutdown_initiated:
            logger.info("🔄 Shutdown already in progress...")
            return
        
        shutdown_initiated = True
        logger.info("🛑 Received shutdown signal, stopping server...")
        
        # Unregister from discovery service if service name provided
        if service_name:
            try:
                unregister_service(service_name)
                logger.info("✅ Unregistered from discovery service")
            except Exception as e:
                logger.error(f"❌ Failed to unregister from discovery service: {e}")
        
        # Stop the server gracefully
        try:
            server.stop(grace=5)
            logger.info("✅ Server stopped successfully")
        except Exception as e:
            logger.error(f"❌ Error stopping server: {e}")
        
        # Force exit after cleanup
        os._exit(0)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    return graceful_shutdown


def get_local_ip() -> str:
    """
    Get the local IP address for service registration.
    
    Uses SERVICE_HOST_IP environment variable if set, otherwise attempts basic IP detection.
    
    Returns:
        str: The IP address to use for service registration
    """
    # Check for environment override
    override_ip = get_env_var("SERVICE_HOST_IP", None)
    if override_ip:
        logger.info(f"✍️ Overriding local_ip with env variable SERVICE_HOST_IP: {override_ip}")
        return override_ip
    
    # Basic IP detection using socket connection
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Connect to a remote address to determine our local IP
            s.connect(("8.8.8.8", 80))
            detected_ip = s.getsockname()[0]
            logger.info(f"🛜  Auto-detected IP: {detected_ip}")
            return detected_ip
    
    except Exception as e:
        logger.warning(f"Failed to detect IP: {e}")
        logger.info("Falling back to localhost (services only accessible locally)")
        logger.info("💡 Set SERVICE_HOST_IP environment variable for reliable cross-machine communication")
        return "127.0.0.1"
    
