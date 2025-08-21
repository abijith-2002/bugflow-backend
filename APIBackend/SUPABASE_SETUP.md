# Supabase Setup Guide for Bug Tracking Application

## Prerequisites

1. **Supabase Account**: Create a free account at [supabase.com](https://supabase.com)
2. **Python Environment**: Python 3.8+ with pip
3. **Project Dependencies**: Install requirements with `pip install -r requirements.txt`

## Step 1: Create Supabase Project

1. Log in to your Supabase dashboard
2. Click "New Project"
3. Choose your organization
4. Fill in project details:
   - **Name**: `bug-tracking-app`
   - **Database Password**: Choose a strong password
   - **Region**: Select the closest region to your users
5. Click "Create new project"
6. Wait for the project to be provisioned (2-3 minutes)

## Step 2: Get Project Credentials

1. Go to your project dashboard
2. Navigate to **Settings** > **API**
3. Copy the following values:
   - **Project URL**: `https://your-project-id.supabase.co`
   - **Anon/Public Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
   - **Service Role Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

⚠️ **Important**: Keep your Service Role Key secret! It has admin privileges.

## Step 3: Configure Environment Variables

### Option A: Automatic Setup (Recommended)

Run the environment setup script:

```bash
cd bugflow-backend/APIBackend
python scripts/setup_env.py
```

This will guide you through setting up all required environment variables.

### Option B: Manual Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your Supabase credentials:
   ```env
   # Supabase Configuration
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_KEY=your_anon_key_here
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

   # JWT Configuration (generate a secure random string)
   JWT_SECRET=your_jwt_secret_key_here

   # Server Configuration
   PORT=8000
   HOST=0.0.0.0
   ENVIRONMENT=development

   # CORS Configuration
   ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
   ```

## Step 4: Initialize Database Schema

Run the database setup script to create all required tables and policies:

```bash
cd bugflow-backend/APIBackend
python scripts/setup_database.py
```

This script will create:

- **Tables**: users, projects, bugs, comments, notifications, audit_logs
- **Row Level Security (RLS) policies**: Proper access control
- **Storage buckets**: For file attachments
- **Triggers**: For automatic timestamp updates
- **Functions**: For user registration handling

## Step 5: Configure Authentication

1. In your Supabase dashboard, go to **Authentication** > **Settings**
2. Configure **Site URL**:
   - Development: `http://localhost:3000`
   - Production: Your actual domain
3. Configure **Redirect URLs**:
   - Add: `http://localhost:3000/**`
   - Add your production URLs when deploying
4. **Email Templates** (optional):
   - Customize signup, reset password emails
   - Use template variables for dynamic URLs

## Step 6: Set Up Row Level Security (RLS) Policies

The setup script automatically creates RLS policies, but here's what they do:

### Users Table
- Users can view and update their own profile
- Admins can view all users

### Projects Table
- All authenticated users can view projects
- Project managers and admins can create projects
- Project creators and admins can update projects
- Only admins can delete projects

### Bugs Table
- All authenticated users can view bugs
- Authenticated users can create bugs
- Bug reporters, assignees, and admins can update bugs
- Only admins can delete bugs

### Comments Table
- All authenticated users can view comments
- Authenticated users can create comments
- Comment authors and admins can update/delete comments

### Notifications Table
- Users can only see their own notifications
- Users can mark their own notifications as read

### Audit Logs Table
- Only admins can view audit logs
- System can create audit logs automatically

## Step 7: Test the Setup

1. **Start the FastAPI server**:
   ```bash
   uvicorn src.api.main:app --reload
   ```

2. **Test the health endpoint**:
   ```bash
   curl http://localhost:8000/health
   ```

3. **Test user registration**:
   ```bash
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "email": "test@example.com",
       "password": "testpassword123",
       "role": "user"
     }'
   ```

## Step 8: Verify Database Structure

1. Go to your Supabase dashboard
2. Navigate to **Database** > **Tables**
3. Verify all tables are created:
   - `users`
   - `projects`
   - `bugs`
   - `comments`
   - `notifications`
   - `audit_logs`

4. Check **Authentication** > **Users** to see if test users are created

## Step 9: Set Up Storage (Optional)

For file attachments, the setup script creates a `bug-attachments` bucket with proper policies. You can:

1. Go to **Storage** in your Supabase dashboard
2. Verify the `bug-attachments` bucket exists
3. Test file uploads through the API

## Troubleshooting

### Common Issues

1. **Connection Error**: Check your SUPABASE_URL and keys
2. **Permission Denied**: Ensure you're using the Service Role Key for admin operations
3. **RLS Blocking Queries**: Check if RLS policies are correctly applied
4. **JWT Errors**: Ensure JWT_SECRET is set and consistent

### Debugging Tips

1. **Enable Supabase Logs**:
   - Go to **Logs** in your dashboard
   - Monitor API requests and errors

2. **Test Policies**:
   - Use the Supabase SQL editor to test queries
   - Check if RLS policies allow your operations

3. **Check Network**:
   - Ensure your server can reach Supabase
   - Verify CORS settings if testing from browser

### Environment Variables Checklist

- [ ] `SUPABASE_URL` - Project URL from dashboard
- [ ] `SUPABASE_KEY` - Anon/public key
- [ ] `SUPABASE_SERVICE_ROLE_KEY` - Service role key (keep secret!)
- [ ] `JWT_SECRET` - Random secure string
- [ ] `PORT` - Server port (default: 8000)
- [ ] `HOST` - Server host (default: 0.0.0.0)
- [ ] `ENVIRONMENT` - Environment name
- [ ] `ALLOWED_ORIGINS` - CORS allowed origins

## Security Best Practices

1. **Environment Variables**: Never commit real credentials to version control
2. **Service Role Key**: Only use on the server, never in client code
3. **CORS**: Configure allowed origins properly for production
4. **RLS Policies**: Test thoroughly to ensure proper access control
5. **JWT Secret**: Use a long, random, secure string
6. **HTTPS**: Always use HTTPS in production

## Next Steps

1. **Frontend Integration**: Configure the React frontend with the same Supabase credentials
2. **Production Deployment**: Set up environment variables in your hosting platform
3. **Monitoring**: Set up logging and monitoring for your application
4. **Backup**: Configure database backups in Supabase
5. **Custom Domain**: Set up a custom domain for your Supabase project (Pro plan)

## Support

- **Supabase Documentation**: [docs.supabase.com](https://docs.supabase.com)
- **FastAPI Documentation**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Community Support**: Join the Supabase Discord or GitHub discussions

---

**Ready to build!** Your Supabase backend is now configured and ready for your bug tracking application.
