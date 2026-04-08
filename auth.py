"""
=============================================================================
File: auth.py
Capabilities:
1. Google ADK OAuth2 Configuration.
2. Token Extraction: Hunts for the Vertex AI token in headers or dictionaries.
3. Service Builder: Returns an authenticated Google Drive API service client.
=============================================================================
"""

import os
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from google.adk.tools import ToolContext
from google.adk.auth import AuthConfig, AuthCredential, AuthCredentialTypes, OAuth2Auth
from fastapi.openapi.models import OAuth2, OAuthFlows, OAuthFlowAuthorizationCode

from .config import get_logger

logger = get_logger(__name__)

# ===========================================================================
# OAUTH CONFIGURATION
# ===========================================================================

# Cleaned up the URL to prevent the "duplicate parameter" error found earlier
auth_scheme = OAuth2(
    flows=OAuthFlows(
        authorizationCode=OAuthFlowAuthorizationCode(
            authorizationUrl="https://accounts.google.com/o/oauth2/v2/auth",
            tokenUrl="https://oauth2.googleapis.com/token",
            scopes={"https://www.googleapis.com/auth/drive": "Google Drive API"}
        )
    )
)

# 1. LOG: Verify Environment Variables are loaded
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

logger.info(f"[AUTH DEBUG] Client ID loaded: {CLIENT_ID[:15]}... (Length: {len(CLIENT_ID)})")
logger.info(f"[AUTH DEBUG] Client Secret loaded: {'***' if CLIENT_SECRET else 'MISSING'}")

auth_credential = AuthCredential(
    auth_type=AuthCredentialTypes.OAUTH2,
    oauth2=OAuth2Auth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
)
AUTH_CONFIG = AuthConfig(auth_scheme=auth_scheme, raw_auth_credential=auth_credential)

def get_drive_service(tool_context: ToolContext):
    """Enhanced logging to find the root cause of token extraction failure."""
    access_token = None
    
    logger.info("--- Starting Token Extraction ---")

    # 2. LOG: Inspect ToolContext Metadata
    # This helps see if headers or auth-info are actually passed into the tool
    try:
        ctx_data = str(tool_context.__dict__)[:500] # Log first 500 chars of context
        logger.debug(f"[AUTH DEBUG] Raw ToolContext snippet: {ctx_data}")
    except Exception as e:
        logger.warning(f"[AUTH DEBUG] Could not stringify ToolContext: {e}")

    # 3. Native ADK Check
    try:
        logger.info("Calling tool_context.get_auth_response...")
        exchanged = tool_context.get_auth_response(AUTH_CONFIG)
        
        if exchanged:
            logger.info(f"[AUTH DEBUG] Received AuthResponse object.")
            if exchanged.oauth2:
                access_token = exchanged.oauth2.access_token
                logger.info(f"[AUTH DEBUG] Access Token found via ADK! (Starts with: {access_token[:10]})")
            else:
                logger.warning("[AUTH DEBUG] AuthResponse exists, but .oauth2 is None.")
        else:
            logger.warning("[AUTH DEBUG] get_auth_response returned None.")
    except Exception as e: 
        logger.error(f"[AUTH DEBUG] Exception in get_auth_response: {str(e)}", exc_info=True)

    # 4. Fallback Search Logging
    if not access_token:
        logger.info("Attempting deep-search for token (ya29...) in context object...")
        try:
            def safe_find(obj, depth=0):
                if depth > 5: return None 
                if isinstance(obj, str):
                    match = re.search(r"(ya29\.[a-zA-Z0-9_\-]+)", obj)
                    if match: return match.group(1)
                    return None
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        res = safe_find(v, depth + 1)
                        if res: return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = safe_find(item, depth + 1)
                        if res: return res
                elif hasattr(obj, '__dict__'): return safe_find(obj.__dict__, depth + 1)
                return None
            
            access_token = safe_find(tool_context)
            if access_token:
                logger.info("[AUTH DEBUG] Token found via deep regex search.")
            else:
                logger.warning("[AUTH DEBUG] Deep regex search found nothing.")
        except Exception as e: 
            logger.error(f"[AUTH DEBUG] Regex search failed: {e}")

    # 5. Build and Return Service
    if access_token:
        try:
            logger.info("Building Drive API service...")
            creds = Credentials(token=access_token, scopes=["https://www.googleapis.com/auth/drive"])
            service = build('drive', 'v3', credentials=creds)
            logger.info("SUCCESS: Drive service is ready.")
            return service
        except Exception as e:
            logger.error(f"Failed to build service with token: {e}")
            return None
    
    # 6. TRIGGER POINT: If we reach here, we must request credentials
    logger.error("RESULT: Failed to extract OAuth token. Requesting credential from UI...")
    try:
        # This signals the UI to show the 'Authorize' button/popup
        tool_context.request_credential(AUTH_CONFIG)
        logger.info("[AUTH DEBUG] request_credential() called.")
    except Exception as e:
        logger.error(f"[AUTH DEBUG] Could not call request_credential: {e}")

    return None