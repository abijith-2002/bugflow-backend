from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from src.database.client import supabase_client
from src.models.user import UserCreate, UserLogin, UserResponse, AuthResponse, UserRole
import jwt
import os
from datetime import datetime, timedelta


class AuthService:
    """Authentication service for user management"""
    
    def __init__(self):
        self.supabase = supabase_client.client
        self.admin_supabase = supabase_client.admin_client
        self.jwt_secret = os.getenv("JWT_SECRET", "your-secret-key")
        self.jwt_algorithm = "HS256"
        self.access_token_expire_minutes = 30

    async def register(self, user_data: UserCreate) -> AuthResponse:
        """Register a new user"""
        try:
            # Create user in Supabase Auth
            auth_response = self.supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password
            })
            
            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create user"
                )
            
            # Create user profile in our custom users table
            user_profile = {
                "id": auth_response.user.id,
                "email": user_data.email,
                "role": user_data.role.value,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            profile_response = self.admin_supabase.table("users").insert(user_profile).execute()
            
            if not profile_response.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile"
                )
            
            # Generate JWT token
            access_token = self._create_access_token(auth_response.user.id, user_data.email, user_data.role)
            
            user_response = UserResponse(
                id=auth_response.user.id,
                email=user_data.email,
                role=user_data.role,
                created_at=datetime.fromisoformat(profile_response.data[0]["created_at"]),
                updated_at=datetime.fromisoformat(profile_response.data[0]["updated_at"])
            )
            
            return AuthResponse(
                access_token=access_token,
                user=user_response
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Registration failed: {str(e)}"
            )

    async def login(self, credentials: UserLogin) -> AuthResponse:
        """Authenticate user and return JWT token"""
        try:
            # Authenticate with Supabase
            auth_response = self.supabase.auth.sign_in_with_password({
                "email": credentials.email,
                "password": credentials.password
            })
            
            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Get user profile from our custom users table
            profile_response = self.supabase.table("users").select("*").eq("id", auth_response.user.id).execute()
            
            if not profile_response.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
            
            profile = profile_response.data[0]
            
            # Generate JWT token
            access_token = self._create_access_token(
                auth_response.user.id, 
                credentials.email, 
                UserRole(profile["role"])
            )
            
            user_response = UserResponse(
                id=profile["id"],
                email=profile["email"],
                role=UserRole(profile["role"]),
                created_at=datetime.fromisoformat(profile["created_at"]),
                updated_at=datetime.fromisoformat(profile["updated_at"])
            )
            
            return AuthResponse(
                access_token=access_token,
                user=user_response
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Login failed: {str(e)}"
            )

    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Get user by ID"""
        try:
            response = self.supabase.table("users").select("*").eq("id", user_id).execute()
            
            if not response.data:
                return None
            
            profile = response.data[0]
            return UserResponse(
                id=profile["id"],
                email=profile["email"],
                role=UserRole(profile["role"]),
                created_at=datetime.fromisoformat(profile["created_at"]),
                updated_at=datetime.fromisoformat(profile["updated_at"])
            )
            
        except Exception:
            return None

    def _create_access_token(self, user_id: str, email: str, role: UserRole) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode = {
            "sub": user_id,
            "email": email,
            "role": role.value,
            "exp": expire
        }
        
        return jwt.encode(to_encode, self.jwt_secret, algorithm=self.jwt_algorithm)

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )


# Global auth service instance
auth_service = AuthService()
