"""
Discovery Client SDK - Functions for service registration and discovery
"""

import requests
import logging
from typing import Optional, Dict
from utils.utils import get_env_var

# Configure logging
logger = logging.getLogger("Discovery Client")
# Set client to DEBUG level - only shows detailed info when needed
logger.setLevel(logging.DEBUG)

class DiscoveryError(Exception):
    """Custom exception for discovery service errors"""
    pass

def get_auth_headers() -> Dict[str, str]:
    """Get authentication headers with API key"""
    api_key = get_env_var("DISCOVERY_API_KEY", None)
    if not api_key:
        raise DiscoveryError("DISCOVERY_API_KEY environment variable must be set")
    
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

def register_service(
    service_name: str,
    service_host: str,
    service_port: int,
    discovery_url: str = get_env_var("DISCOVERY_URL", None),
    metadata: Optional[Dict] = None,
) -> Dict:
    """
    Register a service with the discovery server
    
    Args:
        discovery_url: URL of the discovery server
        service_name: Name of the service to register
        service_host: IP/hostname where the service is running
        service_port: Port where the service is listening
        metadata: Optional metadata dictionary
    
    Returns:
        Response from the discovery server
    
    Raises:
        DiscoveryError: If registration fails
    """
    
    registration_data = {
        "service_name": service_name,
        "host": service_host,
        "port": service_port,
        "metadata": metadata or {}
    }
    
    try:
        headers = get_auth_headers()
        response = requests.post(
            f"{discovery_url}/register",
            json=registration_data,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"✅ Successfully registered '{service_name}' at {service_host}:{service_port}")
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to register service '{service_name}': {e}"
        logger.error(error_msg)
        raise DiscoveryError(error_msg)

def discover_service(
    service_name: str,
    discovery_url: str = get_env_var("DISCOVERY_URL", None),
) -> Dict:
    """
    Discover a service by name
    
    Args:
        discovery_url: URL of the discovery server
        service_name: Name of the service to discover
    
    Returns:
        Service information including host, port, endpoint, and metadata
    
    Raises:
        DiscoveryError: If service is not found or discovery fails
    """
    discovery_url = get_env_var("DISCOVERY_URL", None)
    
    try:
        headers = get_auth_headers()
        response = requests.get(
            f"{discovery_url}/discover/{service_name}",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"🔍 Successfully discovered '{service_name}' at {result['endpoint']}")
        return result
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            error_msg = f"Service '{service_name}' not found in discovery registry"
        else:
            error_msg = f"Failed to discover service '{service_name}': {e}"
        logger.error(error_msg)
        raise DiscoveryError(error_msg)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to discover service '{service_name}': {e}"
        logger.error(error_msg)
        raise DiscoveryError(error_msg)

def get_service_endpoint(
    service_name: str,
    discovery_url: str = get_env_var("DISCOVERY_URL", None),
) -> str:
    """
    Get the endpoint (host:port) for a service
    
    Args:
        discovery_url: URL of the discovery server
        service_name: Name of the service to discover
    
    Returns:
        Service endpoint as "host:port" string
    
    Raises:
        DiscoveryError: If service is not found or discovery fails
    """
    service_info = discover_service(service_name, discovery_url)
    return service_info["endpoint"]

def list_all_services(
    discovery_url: str = get_env_var("DISCOVERY_URL", None),
) -> Dict:
    """
    List all registered services
    
    Args:
        discovery_url: URL of the discovery server
    
    Returns:
        Dictionary containing all registered services
    
    Raises:
        DiscoveryError: If request fails
    """
    try:
        headers = get_auth_headers()
        response = requests.get(
            f"{discovery_url}/services",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"📋 Retrieved {result['count']} registered services")
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to list services: {e}"
        logger.error(error_msg)
        raise DiscoveryError(error_msg)

def unregister_service(
    service_name: str,
    discovery_url: str = get_env_var("DISCOVERY_URL", None),
) -> Dict:
    """
    Unregister a service from the discovery server
    
    Args:
        discovery_url: URL of the discovery server
    
    Returns:
        Response from the discovery server
    
    Raises:
        DiscoveryError: If unregistration fails
    """

    try:
        headers = get_auth_headers()
        response = requests.delete(
            f"{discovery_url}/unregister/{service_name}",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"🗑️  Successfully unregistered '{service_name}'")
        return result
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            error_msg = f"Service '{service_name}' not found in registry"
        else:
            error_msg = f"Failed to unregister service '{service_name}': {e}"
        logger.error(error_msg)
        raise DiscoveryError(error_msg)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to unregister service '{service_name}': {e}"
        logger.error(error_msg)
        raise DiscoveryError(error_msg) 