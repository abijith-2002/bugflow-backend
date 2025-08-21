# Supabase Configuration for BugFlow API

This document describes the Supabase database schema and configuration required for the BugFlow bug tracking application.

## Configuration Status

✅ **Environment Variables**: Configured in `.env` file
✅ **Connection**: Supabase client configured and working
⚠️ **Database Schema**: Requires manual setup (see instructions below)

## Current Environment Configuration

The following environment variables are configured:

- `SUPABASE_URL`: https://zyanjhrlcvcrohfxnlhz.supabase.co
- `SUPABASE_KEY`: Configured with service role key
- `JWT_SECRET_KEY`: Configured for API authentication
- `JWT_ALGORITHM`: HS256
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: 30
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS`: 7

## Database Setup Instructions

**IMPORTANT**: The database tables need to be created manually in your Supabase dashboard.

### Step 1: Access Supabase Dashboard
1. Go to https://supabase.com/dashboard
2. Select your project: `zyanjhrlcvcrohfxnlhz`
3. Navigate to the SQL Editor

### Step 2: Execute Database Setup
1. Copy the contents of `setup_database.sql` (located in the same directory as this file)
2. Paste the SQL script into the Supabase SQL Editor
3. Click "Run" to execute the script

This will create:
- All required tables (users, projects, bugs, etc.)
- Proper indexes for performance
- Row Level Security policies
- Triggers for timestamp updates
- Sample admin user and project

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'developer' CHECK (role IN ('admin', 'project_manager', 'developer', 'tester', 'viewer')),
    is_active BOOLEAN DEFAULT true,
    avatar_url TEXT,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Projects Table
```sql
CREATE TABLE projects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'completed', 'archived')),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Project Members Table
```sql
CREATE TABLE project_members (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'developer',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_id, user_id)
);
```

### Bugs Table
```sql
CREATE TABLE bugs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed', 'reopened')),
    priority VARCHAR(50) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    reported_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Bug Comments Table
```sql
CREATE TABLE bug_comments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    bug_id UUID NOT NULL REFERENCES bugs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Notifications Table
```sql
CREATE TABLE notifications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL CHECK (type IN ('bug_assigned', 'bug_updated', 'project_assigned', 'comment_added', 'status_changed')),
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    related_id UUID,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Audit Logs Table
```sql
CREATE TABLE audit_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID NOT NULL,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Indexes

All necessary indexes are created automatically by the setup script for optimal performance:

- Users: email, role, is_active
- Projects: owner_id, status
- Project members: project_id, user_id
- Bugs: project_id, reported_by, assigned_to, status, priority
- Bug comments: bug_id, user_id
- Notifications: user_id, is_read, type
- Audit logs: user_id, resource_type, resource_id, created_at

## Row Level Security (RLS) Policies

RLS is enabled on all tables with appropriate policies:

- Users can view and update their own profiles
- Users can view projects they own or are members of
- Users can view bugs in their accessible projects
- Users can view and update their own notifications

## API Integration

### FastAPI Configuration
The FastAPI application is configured to connect to Supabase using:

1. **Database Connection**: `src/core/database.py`
   - Initializes Supabase client with environment variables
   - Provides connection testing functionality
   - Offers database client dependency for FastAPI routes

2. **Configuration**: `src/core/config.py`
   - Reads all Supabase and JWT settings from environment variables
   - Validates required configuration values

3. **Authentication**: `src/utils/auth.py`
   - JWT token creation and verification
   - Password hashing and verification
   - Token pair generation for access/refresh tokens

### Usage Examples

```python
# Get database client
from src.core.database import get_database

# In a FastAPI route
@app.get("/users")
async def get_users(db = Depends(get_database)):
    result = db.table("users").select("*").execute()
    return result.data
```

## Security Configuration

### Authentication Flow
1. User registers/logs in through `/auth/login` endpoint
2. API generates JWT tokens using configured secret key
3. Subsequent requests include JWT token in Authorization header
4. API validates token and extracts user information
5. Database operations use service role key with application-level authorization

### Environment Security
- Service role key provides full database access for API operations
- JWT secret key should be changed in production
- All sensitive operations are logged in audit_logs table

## Backup and Maintenance

1. **Automated Backups**: Enabled in Supabase dashboard
2. **Monitoring**: Use Supabase dashboard for performance monitoring
3. **Audit Trail**: All user actions are logged in audit_logs table
4. **Cleanup**: Consider archiving old audit logs and resolved bugs periodically

## Troubleshooting

### Connection Issues
1. Verify SUPABASE_URL and SUPABASE_KEY in `.env` file
2. Check network connectivity to Supabase
3. Ensure service role key has proper permissions

### Database Issues
1. Verify tables exist by checking Supabase dashboard
2. Run setup_database.sql if tables are missing
3. Check RLS policies if access is denied

### API Issues
1. Test database connection using health check endpoint: `GET /health/database`
2. Check application logs for specific error messages
3. Verify JWT configuration for authentication issues

## Next Steps

After setting up the database:

1. ✅ Execute `setup_database.sql` in Supabase dashboard
2. ✅ Test API connection with `GET /health/database`
3. ✅ Create first admin user via `POST /auth/register`
4. ✅ Test authentication flow with `POST /auth/login`
5. ✅ Begin using API endpoints for project and bug management

## API Endpoints

The following endpoints are available once the database is set up:

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - User logout
- `PUT /auth/password` - Update password

### Users
- `GET /users` - List users (with pagination)
- `GET /users/{user_id}` - Get user profile
- `POST /users` - Create user (admin only)
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user (admin only)

### Projects
- `GET /projects` - List projects
- `GET /projects/{project_id}` - Get project details
- `POST /projects` - Create project
- `PUT /projects/{project_id}` - Update project
- `DELETE /projects/{project_id}` - Delete project
- `GET /projects/{project_id}/members` - Get project members
- `POST /projects/{project_id}/members/{user_id}` - Add member
- `DELETE /projects/{project_id}/members/{user_id}` - Remove member

### Bugs
- `GET /bugs` - List bugs (with filtering)
- `GET /bugs/{bug_id}` - Get bug details
- `POST /bugs` - Create bug
- `PUT /bugs/{bug_id}` - Update bug
- `DELETE /bugs/{bug_id}` - Delete bug
- `GET /bugs/{bug_id}/comments` - Get bug comments
- `POST /bugs/{bug_id}/comments` - Add comment

### Dashboard
- `GET /dashboard/stats` - Get dashboard statistics
- `GET /dashboard/activity` - Get recent activity

### Notifications
- `GET /notifications` - List user notifications
- `GET /notifications/unread/count` - Get unread count
- `PUT /notifications/{notification_id}` - Mark as read/unread
- `DELETE /notifications/{notification_id}` - Delete notification

## Production Checklist

Before deploying to production:

- [ ] Change JWT_SECRET_KEY to a secure random value
- [ ] Update admin user password in database
- [ ] Configure proper CORS origins
- [ ] Enable Supabase backups
- [ ] Set up monitoring and alerting
- [ ] Review and adjust RLS policies as needed
- [ ] Configure rate limiting
- [ ] Set up SSL/TLS certificates
