"""
Centralized logging configuration for the Relator system
"""

import logging
import os

def setup_logging(verbose: bool = None):
    """
    Setup logging configuration for the entire application
    
    Args:
        verbose: If True, shows DEBUG level logs. If None, uses VERBOSE env var
    """
    # Check environment variable if not explicitly set
    if verbose is None:
        verbose = os.getenv("VERBOSE", "false").lower() in ("true", "1", "yes")
    
    # Set root logger level
    root_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=root_level,
        format="%(levelname)s:[%(name)s]:%(message)s"
    )
    
    # Configure specific loggers
    if not verbose:
        # In normal mode, reduce noise from client libraries
        logging.getLogger("Discovery Client").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # Always keep important service logs at INFO level
    logging.getLogger("Discovery Utils").setLevel(logging.INFO)
    logging.getLogger("Discovery Server").setLevel(logging.INFO)
    logging.getLogger("Module A").setLevel(logging.INFO)
    logging.getLogger("Module B").setLevel(logging.INFO)
    logging.getLogger("Module C").setLevel(logging.INFO)
    logging.getLogger("Module D").setLevel(logging.INFO) 