import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from postgrest.exceptions import APIError

from ..config import get_settings
from ..schemas.auth import UserProfile, SignupRequest, LoginRequest
from .supabase_client import supabase_anon_client, supabase_client

settings = get_settings()


class AuthService:
    def __init__(self):
        self.supabase_anon = supabase_anon_client
        self.supabase = supabase_client
    
    async def signup_user(self, signup_data: SignupRequest) -> Dict[str, Any]:
        """
        Register a new user with Supabase Auth
        
        Args:
            signup_data: User signup information
            
        Returns:
            Dict containing user data and session information
            
        Raises:
            ValueError: If registration fails
        """
        try:
            # Sign up user with Supabase Auth
            auth_response = self.supabase_anon.auth.sign_up({
                "email": signup_data.email,
                "password": signup_data.password,
                "options": {
                    "data": {
                        "first_name": signup_data.first_name,
                        "last_name": signup_data.last_name
                    }
                }
            })
            
            if auth_response.user is None:
                raise ValueError("User registration failed")
            
            user = auth_response.user
            
            # Create user profile in our custom table
            try:
                # Insert user profile (this will be created when Supabase is properly configured)
                # For now, we'll just prepare the data
                pass
                
            except Exception:
                print("Profile creation warning: table not yet configured")
            
            # Generate our own JWT token
            access_token = self._create_access_token(
                data={"sub": user.email, "user_id": user.id}
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.jwt_access_token_expire_minutes * 60,
                "user": UserProfile(
                    id=user.id,
                    email=user.email,
                    first_name=signup_data.first_name,
                    last_name=signup_data.last_name,
                    created_at=datetime.utcnow()
                )
            }
            
        except APIError as e:
            raise ValueError(f"Registration failed: {e.message}")
        except Exception as e:
            raise ValueError(f"Registration failed: {str(e)}")
    
    async def login_user(self, login_data: LoginRequest) -> Dict[str, Any]:
        """
        Authenticate user with Supabase Auth
        
        Args:
            login_data: User login credentials
            
        Returns:
            Dict containing user data and session information
            
        Raises:
            ValueError: If authentication fails
        """
        try:
            # Sign in with Supabase Auth
            auth_response = self.supabase_anon.auth.sign_in_with_password({
                "email": login_data.email,
                "password": login_data.password
            })
            
            if auth_response.user is None:
                raise ValueError("Invalid credentials")
            
            user = auth_response.user
            
            # Get user profile data (when available)
            user_profile = UserProfile(
                id=user.id,
                email=user.email,
                first_name=user.user_metadata.get("first_name"),
                last_name=user.user_metadata.get("last_name"),
                avatar_url=user.user_metadata.get("avatar_url"),
                created_at=datetime.fromisoformat(user.created_at.replace('Z', '+00:00'))
            )
            
            # Generate our own JWT token
            access_token = self._create_access_token(
                data={"sub": user.email, "user_id": user.id}
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.jwt_access_token_expire_minutes * 60,
                "user": user_profile
            }
            
        except APIError as e:
            raise ValueError("Invalid credentials")
        except Exception as e:
            raise ValueError(f"Login failed: {str(e)}")
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and return user information
        
        Args:
            token: JWT token to verify
            
        Returns:
            Dict containing user information if token is valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token, 
                settings.jwt_secret_key, 
                algorithms=[settings.jwt_algorithm]
            )
            
            user_email = payload.get("sub")
            user_id = payload.get("user_id")
            
            if user_email is None or user_id is None:
                return None
            
            return {
                "user_id": user_id,
                "email": user_email
            }
            
        except jwt.PyJWTError:
            return None
    
    def _create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.jwt_access_token_expire_minutes
            )
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.jwt_secret_key, 
            algorithm=settings.jwt_algorithm
        )
        return encoded_jwt


# Global auth service instance
auth_service = AuthService()
