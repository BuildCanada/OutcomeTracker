#!/usr/bin/env python3
"""
Firebase Initialization Utility

Provides a standardized, robust Firebase initialization pattern for all scripts.
Based on the pattern used in consolidated_promise_enrichment.py.

This utility tries default credentials first (works in Google Cloud environments),
then falls back to service account key files if default fails.
"""

import firebase_admin
from firebase_admin import firestore, credentials
import os
import logging
import time
from typing import Optional, Tuple

# Set up logger
logger = logging.getLogger(__name__)

def initialize_firebase_admin(app_name: Optional[str] = None) -> Tuple[firestore.Client, bool]:
    """
    Initialize Firebase Admin SDK with robust credential handling.
    
    Args:
        app_name: Optional custom app name for the Firebase app
        
    Returns:
        Tuple of (firestore_client, success_flag)
        
    Raises:
        SystemExit: If initialization fails completely
    """
    db = None
    
    # Generate unique app name if not provided
    if app_name is None:
        app_name = f"firebase_app_{int(time.time())}"
    
    # Check if Firebase is already initialized
    if not firebase_admin._apps:
        logger.info("No Firebase apps initialized yet, starting fresh initialization")
    else:
        logger.info(f"Found {len(firebase_admin._apps)} existing Firebase apps")
    
    # PHASE 1: Try default credentials (works in Google Cloud environments)
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        else:
            # Create a new app with unique name if apps already exist
            firebase_admin.initialize_app(name=app_name)
            
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        
        # Get the appropriate app
        if not firebase_admin._apps or len(firebase_admin._apps) == 1:
            db = firestore.client()
        else:
            db = firestore.client(app=firebase_admin.get_app(name=app_name))
            
        return db, True
        
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        
        # PHASE 2: Try service account key file
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                
                if not os.path.exists(cred_path):
                    raise FileNotFoundError(f"Service account key file not found at: {cred_path}")
                
                cred = credentials.Certificate(cred_path)
                
                # Handle app naming to avoid conflicts
                try:
                    if not firebase_admin._apps:
                        firebase_admin.initialize_app(cred)
                        app_instance = firebase_admin.get_app()
                    else:
                        # Create unique app name to avoid ValueError
                        unique_app_name = f"{app_name}_{int(time.time())}"
                        firebase_admin.initialize_app(cred, name=unique_app_name)
                        app_instance = firebase_admin.get_app(name=unique_app_name)
                        app_name = unique_app_name
                        
                except ValueError as ve:
                    # App already exists, try with different name
                    logger.warning(f"App name conflict: {ve}, trying with unique timestamp")
                    unique_app_name = f"{app_name}_{int(time.time() * 1000)}"
                    firebase_admin.initialize_app(cred, name=unique_app_name)
                    app_instance = firebase_admin.get_app(name=unique_app_name)
                    app_name = unique_app_name

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account (app: {app_name}).")
                
                db = firestore.client(app=app_instance)
                return db, True
                
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

    # PHASE 3: Final fallback attempt with alternative environment variables
    alt_cred_path = os.getenv('FIREBASE_ADMIN_SDK_PATH')  # Used by some older scripts
    if alt_cred_path and os.path.exists(alt_cred_path):
        try:
            logger.info(f"Attempting Firebase init with alternative service account path: {alt_cred_path}")
            cred = credentials.Certificate(alt_cred_path)
            
            unique_app_name = f"{app_name}_alt_{int(time.time())}"
            firebase_admin.initialize_app(cred, name=unique_app_name)
            
            project_id_alt = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Alt Service Account]')
            logger.info(f"Connected to CLOUD Firestore (Project: {project_id_alt}) via alternative service account.")
            
            db = firestore.client(app=firebase_admin.get_app(name=unique_app_name))
            return db, True
            
        except Exception as e_alt:
            logger.critical(f"Firebase init with alternative service account failed: {e_alt}", exc_info=True)

    # If we get here, all initialization attempts failed
    logger.critical("CRITICAL: Failed to obtain Firestore client. All credential methods failed.")
    logger.critical("Please ensure one of the following:")
    logger.critical("1. Running in Google Cloud environment with default credentials")
    logger.critical("2. FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable is set")
    logger.critical("3. FIREBASE_ADMIN_SDK_PATH environment variable is set")
    logger.critical("4. GOOGLE_APPLICATION_CREDENTIALS environment variable is set")
    
    raise SystemExit("Exiting: Firestore client not available.")

def get_firestore_client(app_name: Optional[str] = None) -> firestore.Client:
    """
    Convenience function to get a Firestore client with robust initialization.
    
    Args:
        app_name: Optional custom app name for the Firebase app
        
    Returns:
        Initialized Firestore client
        
    Raises:
        SystemExit: If initialization fails
    """
    db, success = initialize_firebase_admin(app_name)
    if not success:
        raise SystemExit("Failed to initialize Firebase")
    return db

def log_firebase_info():
    """Log information about current Firebase apps and configuration."""
    logger.info(f"Current Firebase apps: {len(firebase_admin._apps)}")
    for app_name, app in firebase_admin._apps.items():
        logger.info(f"  - App: {app_name}, Project: {getattr(app, 'project_id', 'Unknown')}")
    
    # Log environment variables (without values for security)
    env_vars = [
        'FIREBASE_PROJECT_ID',
        'FIREBASE_SERVICE_ACCOUNT_KEY_PATH', 
        'FIREBASE_ADMIN_SDK_PATH',
        'GOOGLE_APPLICATION_CREDENTIALS'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"Environment: {var} is set")
        else:
            logger.debug(f"Environment: {var} is not set")

# Example usage and testing
if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    
    print("Testing Firebase initialization...")
    log_firebase_info()
    
    try:
        db = get_firestore_client("test_app")
        print("✅ Firebase initialization successful!")
        print(f"Firestore client: {db}")
        
        # Test basic connectivity
        collections = list(db.collections())
        print(f"Found {len(collections)} collections in database")
        
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}") 