#!/usr/bin/env python3
"""
Environment Setup Script for Bug Tracking Application

This script helps configure the environment variables for the application.
"""

import os
import secrets
import string

def generate_jwt_secret(length=64):
    """Generate a secure JWT secret key"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(characters) for _ in range(length))

def create_env_file():
    """Create .env file with proper configuration"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    
    print("🔧 Setting up environment variables")
    print("=" * 50)
    
    # Get Supabase configuration
    print("\n📊 Supabase Configuration")
    print("Please provide your Supabase project details:")
    print("(You can find these in your Supabase project dashboard)")
    
    supabase_url = input("Supabase URL: ").strip()
    supabase_anon_key = input("Supabase Anon Key: ").strip()
    supabase_service_key = input("Supabase Service Role Key: ").strip()
    
    # Generate JWT secret
    jwt_secret = generate_jwt_secret()
    print(f"\n🔐 Generated JWT Secret: {jwt_secret[:20]}...")
    
    # Server configuration
    print("\n⚙️ Server Configuration")
    port = input("Port (default: 8000): ").strip() or "8000"
    host = input("Host (default: 0.0.0.0): ").strip() or "0.0.0.0"
    environment = input("Environment (default: development): ").strip() or "development"
    
    # CORS configuration
    print("\n🌐 CORS Configuration")
    print("Enter allowed origins (comma-separated):")
    print("Default: http://localhost:3000,http://localhost:3001")
    allowed_origins = input("Allowed Origins: ").strip() or "http://localhost:3000,http://localhost:3001"
    
    # Create .env content
    env_content = f"""# Supabase Configuration
SUPABASE_URL={supabase_url}
SUPABASE_KEY={supabase_anon_key}
SUPABASE_SERVICE_ROLE_KEY={supabase_service_key}

# JWT Configuration
JWT_SECRET={jwt_secret}

# Server Configuration
PORT={port}
HOST={host}
ENVIRONMENT={environment}

# CORS Configuration
ALLOWED_ORIGINS={allowed_origins}
"""
    
    # Write to .env file
    try:
        with open(env_path, 'w') as f:
            f.write(env_content)
        
        print(f"\n✅ Environment file created successfully at: {env_path}")
        print("\n🚀 Next steps:")
        print("1. Review the .env file and make any necessary adjustments")
        print("2. Run 'python scripts/setup_database.py' to initialize the database")
        print("3. Start the FastAPI application with 'uvicorn src.api.main:app --reload'")
        
    except Exception as e:
        print(f"\n❌ Error creating .env file: {e}")

def main():
    """Main setup function"""
    print("🏗️ Bug Tracking Application - Environment Setup")
    print("=" * 60)
    
    create_env_file()

if __name__ == "__main__":
    main()
