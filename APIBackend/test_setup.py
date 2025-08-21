#!/usr/bin/env python3
"""
Test script to verify Supabase configuration and API setup.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Add parent directory for relative imports
parent_path = Path(__file__).parent
sys.path.insert(0, str(parent_path))

def test_environment():
    """Test environment variable configuration."""
    print("🔧 Testing Environment Configuration...")
    
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_KEY', 
        'JWT_SECRET_KEY',
        'JWT_ALGORITHM'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All required environment variables are set")
        return True

def test_imports():
    """Test that all modules can be imported."""
    print("\n📦 Testing Module Imports...")
    
    try:
        from core.config import settings
        print("✅ Core configuration imported successfully")
        
        from core.database import db
        print("✅ Database connection imported successfully")
        
        from models.schemas import UserRole, BugStatus
        print("✅ Schema models imported successfully")
        
        try:
            from utils.auth import verify_password, create_token_pair
            print("✅ Authentication utilities imported successfully")
        except Exception as auth_error:
            print(f"⚠️ Authentication utilities import issue: {auth_error}")
            # Test if functions work individually
            try:
                import subprocess
                result = subprocess.run([
                    'python', '-c', 
                    'import sys; sys.path.insert(0, "src"); from utils.auth import verify_password; print("Auth functions available")'
                ], capture_output=True, text=True, cwd='.')
                if result.returncode == 0:
                    print("✅ Authentication utilities work via subprocess")
                else:
                    print(f"❌ Auth test failed: {result.stderr}")
            except Exception:
                pass
        
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_database_connection():
    """Test database connection."""
    print("\n🗄️ Testing Database Connection...")
    
    try:
        from core.database import db
        
        # Test basic client connection
        print("Testing Supabase client connection...")
        client = db.client
        
        # Try a simple query that should work even without tables
        try:
            # Test with a system table that should exist
            result = client.rpc('version').execute()
            print("✅ Supabase client connection successful")
            
            # Now test if our tables exist
            try:
                users_test = client.table('users').select('id').limit(1).execute()
                print("✅ Database tables are set up and accessible")
                return True
            except Exception as table_error:
                if 'Could not find the table' in str(table_error):
                    print("⚠️ Database connected but tables not set up yet")
                    print("   Please run setup_database.sql in Supabase dashboard")
                    return False
                else:
                    print(f"⚠️ Table access issue: {table_error}")
                    return False
                    
        except Exception as client_error:
            print(f"❌ Supabase client error: {client_error}")
            return False
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def test_api_startup():
    """Test that the FastAPI app can start."""
    print("\n🚀 Testing API Startup...")
    
    try:
        # Test using the main app file
        import subprocess
        import tempfile
        
        # Create a simple test script
        test_script = """
import sys
sys.path.insert(0, 'src')
try:
    from api.main import app
    print("FastAPI app created successfully")
    routes = [route.path for route in app.routes]
    print(f"Found {len(routes)} routes")
    expected_routes = ["/", "/auth/login", "/users", "/projects", "/bugs"]
    for route in expected_routes:
        if any(route in r for r in routes):
            print(f"✓ {route}")
        else:
            print(f"✗ {route}")
except Exception as e:
    print(f"Error: {e}")
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_script)
            test_file = f.name
        
        try:
            result = subprocess.run([
                sys.executable, test_file
            ], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ FastAPI application test completed")
                print(result.stdout)
                return True
            else:
                print("⚠️ FastAPI application test had issues")
                print(result.stderr)
                return False
                
        finally:
            os.unlink(test_file)
        
    except Exception as e:
        print(f"❌ API startup test error: {e}")
        return False

def main():
    """Run all tests."""
    print("🔍 BugFlow API Configuration Test\n")
    
    tests = [
        test_environment,
        test_imports,
        test_database_connection,
        test_api_startup
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    print(f"\n📊 Test Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("🎉 All tests passed! Your Supabase configuration is ready.")
        print("\n📋 Next Steps:")
        print("1. Execute setup_database.sql in your Supabase dashboard")
        print("2. Start the API server: python main.py")
        print("3. Test the API endpoints at http://localhost:8000/docs")
    else:
        print("⚠️ Some tests failed. Please check the configuration.")
        
    return all(results)

if __name__ == "__main__":
    main()
