# backend/app/middleware/auth.py
from fastapi import Request, HTTPException, Depends
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
import uuid
from typing import Optional

# ⚠️ REPLACE with your actual Clerk frontend URL when ready
# Get this from: https://dashboard.clerk.com -> Your App -> API Keys
CLERK_FRONTEND_API = "https://your-app-name.clerk.accounts.dev"

# Configure Clerk JWT validation
clerk_config = ClerkConfig(
    jwks_url=f"{CLERK_FRONTEND_API}/.well-known/jwks.json",
    auto_error=False,  # Allow fallback to guest
    add_state=True
)

clerk_auth = ClerkHTTPBearer(config=clerk_config)

def get_clerk_identity(credentials: HTTPAuthorizationCredentials = Depends(clerk_auth)):
    """
    Returns user identity from Clerk JWT or guest info
    """
    if credentials and credentials.decoded:
        claims = credentials.decoded
        user_id = claims.get("sub")
        if user_id:
            return {
                "user_id": user_id, 
                "claims": claims, 
                "is_logged_in": True,
                "email": claims.get("email", ""),
                "username": claims.get("username", claims.get("name", ""))
            }
    
    # Guest user fallback
    return {
        "user_id": None, 
        "claims": None, 
        "is_logged_in": False,
        "email": "",
        "username": ""
    }

def get_user_identity(request: Request) -> dict:
    """
    Extract user identity from request (for guest users)
    Handles X-Guest-ID header and generates new guest IDs if needed
    """
    guest_id = request.headers.get("X-Guest-ID")
    
    if not guest_id:
        # Generate new guest ID
        guest_id = f"guest_{uuid.uuid4().hex[:12]}"
    
    return {
        "user_id": guest_id,
        "is_guest": True,
        "email": f"{guest_id}@guest.local",
        "username": f"Guest_{guest_id[-8:]}"
    }

def determine_user_identity(request: Request, identity: dict = None) -> tuple:
    """
    Determine final user identity combining Clerk auth and guest fallback
    Returns: (user_id, is_guest, email, username, guest_id_for_header)
    """
    if identity and identity.get("is_logged_in"):
        # Authenticated user via Clerk
        return (
            identity["user_id"],
            False,  # is_guest
            identity["email"],
            identity["username"],
            None  # no guest ID needed
        )
    else:
        # Guest user
        guest_info = get_user_identity(request)
        return (
            guest_info["user_id"],
            True,  # is_guest
            guest_info["email"],
            guest_info["username"],
            guest_info["user_id"]  # return guest_id for response header
        )