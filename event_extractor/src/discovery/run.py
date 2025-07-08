from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging
from typing import Dict, Optional
import uvicorn
import os
from utils.logging_config import setup_logging
from utils.utils import get_env_var

# Configure logging
setup_logging()
logger = logging.getLogger("Discovery Server")

# Security setup
security = HTTPBearer()

def get_api_key() -> str:
    """Get API key from environment variables"""
    api_key = get_env_var("DISCOVERY_API_KEY", None)
    if not api_key:
        raise ValueError("DISCOVERY_API_KEY environment variable must be set")
    return api_key

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify the provided API key"""
    try:
        api_key = get_api_key()
        if credentials.credentials != api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return True
    except ValueError as e:
        logger.error(f"Authentication configuration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not properly configured"
        )

app = FastAPI(title="Relator Discovery Service", version="1.0.0")

# Simple in-memory dictionary to store service information
services_registry: Dict[str, dict] = {}

class ServiceInfo(BaseModel):
    """Service information model"""
    host: str
    port: int
    metadata: Optional[dict] = None

class ServiceRegistration(BaseModel):
    """Service registration request model"""
    service_name: str
    host: str
    port: int
    metadata: Optional[dict] = None

@app.get("/")
def root():
    """Health check endpoint (public - no auth required)"""
    return {"status": "Discovery Service is running", "registered_services": len(services_registry)}

@app.post("/register")
def register_service(registration: ServiceRegistration, _: bool = Depends(verify_api_key)):
    """
    Register a service in the discovery registry
    
    Args:
        registration: Service registration information
    
    Returns:
        Success message with registration details
    """
    service_info = {
        "host": registration.host,
        "port": registration.port,
        "metadata": registration.metadata or {},
        "endpoint": f"{registration.host}:{registration.port}"
    }
    
    services_registry[registration.service_name] = service_info
    
    logger.info(f"✅ Registered service '{registration.service_name}' at {service_info['endpoint']}")
    
    return {
        "message": f"Service '{registration.service_name}' registered successfully",
        "service_name": registration.service_name,
        "endpoint": service_info["endpoint"]
    }

@app.get("/discover/{service_name}")
def discover_service(service_name: str, _: bool = Depends(verify_api_key)):
    """
    Discover a service by name
    
    Args:
        service_name: Name of the service to discover
    
    Returns:
        Service information including host, port, and metadata
    
    Raises:
        HTTPException: If service is not found
    """
    if service_name not in services_registry:
        logger.warning(f"❌ Service '{service_name}' not found in registry")
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    service_info = services_registry[service_name]
    logger.info(f"🔍 Service '{service_name}' discovered at {service_info['endpoint']}")
    
    return {
        "service_name": service_name,
        **service_info
    }

@app.get("/services")
def list_services(_: bool = Depends(verify_api_key)):
    """
    List all registered services
    
    Returns:
        Dictionary of all registered services
    """
    logger.info(f"📋 Listed all services: {list(services_registry.keys())}")
    return {
        "services": services_registry,
        "count": len(services_registry)
    }

@app.delete("/unregister/{service_name}")
def unregister_service(service_name: str, _: bool = Depends(verify_api_key)):
    """
    Unregister a service from the registry
    
    Args:
        service_name: Name of the service to unregister
    
    Returns:
        Success message
    
    Raises:
        HTTPException: If service is not found
    """
    if service_name not in services_registry:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    del services_registry[service_name]
    logger.info(f"🗑️  Unregistered service '{service_name}'")
    
    return {"message": f"Service '{service_name}' unregistered successfully"}

def main():
    """Run the discovery server"""
    uvicorn.run(
        "discovery.run:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main() 