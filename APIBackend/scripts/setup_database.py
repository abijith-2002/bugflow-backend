#!/usr/bin/env python3
"""
Supabase Database Setup Script for Bug Tracking Application

This script creates all required tables, RLS policies, and initial configuration
for the bug tracking application.

Run this script after setting up your Supabase environment variables.
"""

import os
import sys
from supabase import create_client, Client
from typing import Optional

def get_supabase_client() -> Optional[Client]:
    """Get Supabase client with service role key for admin operations"""
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not service_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables are required")
        print("Please set these variables in your .env file or environment")
        return None
    
    return create_client(url, service_key)

def create_users_table(supabase: Client):
    """Create users table with additional profile fields"""
    print("Creating users table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS public.users (
        id UUID REFERENCES auth.users(id) PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin', 'project_manager')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Enable RLS
    ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

    -- Create policies
    CREATE POLICY "Users can view own profile" ON public.users
        FOR SELECT USING (auth.uid() = id);

    CREATE POLICY "Users can update own profile" ON public.users
        FOR UPDATE USING (auth.uid() = id);

    CREATE POLICY "Admins can view all users" ON public.users
        FOR SELECT USING (
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role = 'admin'
            )
        );

    -- Create function to handle new user registration
    CREATE OR REPLACE FUNCTION public.handle_new_user()
    RETURNS TRIGGER AS $$
    BEGIN
        INSERT INTO public.users (id, email, role)
        VALUES (NEW.id, NEW.email, 'user');
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;

    -- Create trigger for new user registration
    DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
    CREATE TRIGGER on_auth_user_created
        AFTER INSERT ON auth.users
        FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Users table created successfully")
    except Exception as e:
        print(f"Error creating users table: {e}")

def create_projects_table(supabase: Client):
    """Create projects table"""
    print("Creating projects table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS public.projects (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        created_by UUID REFERENCES public.users(id) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Enable RLS
    ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

    -- Create policies
    CREATE POLICY "All authenticated users can view projects" ON public.projects
        FOR SELECT USING (auth.role() = 'authenticated');

    CREATE POLICY "Project managers and admins can create projects" ON public.projects
        FOR INSERT WITH CHECK (
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role IN ('admin', 'project_manager')
            )
        );

    CREATE POLICY "Project creators and admins can update projects" ON public.projects
        FOR UPDATE USING (
            created_by = auth.uid() OR
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role = 'admin'
            )
        );

    CREATE POLICY "Admins can delete projects" ON public.projects
        FOR DELETE USING (
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role = 'admin'
            )
        );
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Projects table created successfully")
    except Exception as e:
        print(f"Error creating projects table: {e}")

def create_bugs_table(supabase: Client):
    """Create bugs table"""
    print("Creating bugs table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS public.bugs (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
        project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE NOT NULL,
        assigned_to UUID REFERENCES public.users(id),
        reported_by UUID REFERENCES public.users(id) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Enable RLS
    ALTER TABLE public.bugs ENABLE ROW LEVEL SECURITY;

    -- Create policies
    CREATE POLICY "All authenticated users can view bugs" ON public.bugs
        FOR SELECT USING (auth.role() = 'authenticated');

    CREATE POLICY "Authenticated users can create bugs" ON public.bugs
        FOR INSERT WITH CHECK (auth.role() = 'authenticated');

    CREATE POLICY "Bug reporters, assignees, and admins can update bugs" ON public.bugs
        FOR UPDATE USING (
            reported_by = auth.uid() OR
            assigned_to = auth.uid() OR
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role IN ('admin', 'project_manager')
            )
        );

    CREATE POLICY "Admins can delete bugs" ON public.bugs
        FOR DELETE USING (
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role = 'admin'
            )
        );
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Bugs table created successfully")
    except Exception as e:
        print(f"Error creating bugs table: {e}")

def create_comments_table(supabase: Client):
    """Create comments table"""
    print("Creating comments table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS public.comments (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        bug_id UUID REFERENCES public.bugs(id) ON DELETE CASCADE NOT NULL,
        user_id UUID REFERENCES public.users(id) NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Enable RLS
    ALTER TABLE public.comments ENABLE ROW LEVEL SECURITY;

    -- Create policies
    CREATE POLICY "All authenticated users can view comments" ON public.comments
        FOR SELECT USING (auth.role() = 'authenticated');

    CREATE POLICY "Authenticated users can create comments" ON public.comments
        FOR INSERT WITH CHECK (auth.role() = 'authenticated');

    CREATE POLICY "Comment authors and admins can update comments" ON public.comments
        FOR UPDATE USING (
            user_id = auth.uid() OR
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role = 'admin'
            )
        );

    CREATE POLICY "Comment authors and admins can delete comments" ON public.comments
        FOR DELETE USING (
            user_id = auth.uid() OR
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role = 'admin'
            )
        );
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Comments table created successfully")
    except Exception as e:
        print(f"Error creating comments table: {e}")

def create_notifications_table(supabase: Client):
    """Create notifications table"""
    print("Creating notifications table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS public.notifications (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('bug_assigned', 'bug_updated', 'comment_added')),
        read BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Enable RLS
    ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

    -- Create policies
    CREATE POLICY "Users can view own notifications" ON public.notifications
        FOR SELECT USING (user_id = auth.uid());

    CREATE POLICY "System can create notifications" ON public.notifications
        FOR INSERT WITH CHECK (true);

    CREATE POLICY "Users can update own notifications" ON public.notifications
        FOR UPDATE USING (user_id = auth.uid());

    CREATE POLICY "Users can delete own notifications" ON public.notifications
        FOR DELETE USING (user_id = auth.uid());
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Notifications table created successfully")
    except Exception as e:
        print(f"Error creating notifications table: {e}")

def create_audit_logs_table(supabase: Client):
    """Create audit logs table"""
    print("Creating audit_logs table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS public.audit_logs (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id UUID REFERENCES public.users(id),
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id UUID NOT NULL,
        old_values JSONB,
        new_values JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Enable RLS
    ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

    -- Create policies
    CREATE POLICY "Admins can view all audit logs" ON public.audit_logs
        FOR SELECT USING (
            EXISTS (
                SELECT 1 FROM public.users
                WHERE id = auth.uid() AND role = 'admin'
            )
        );

    CREATE POLICY "System can create audit logs" ON public.audit_logs
        FOR INSERT WITH CHECK (true);
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Audit logs table created successfully")
    except Exception as e:
        print(f"Error creating audit logs table: {e}")

def create_updated_at_trigger(supabase: Client):
    """Create updated_at trigger function"""
    print("Creating updated_at trigger...")
    
    sql = """
    -- Create function to update updated_at timestamp
    CREATE OR REPLACE FUNCTION public.update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- Create triggers for tables with updated_at column
    DROP TRIGGER IF EXISTS update_users_updated_at ON public.users;
    CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON public.users
        FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

    DROP TRIGGER IF EXISTS update_projects_updated_at ON public.projects;
    CREATE TRIGGER update_projects_updated_at
        BEFORE UPDATE ON public.projects
        FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

    DROP TRIGGER IF EXISTS update_bugs_updated_at ON public.bugs;
    CREATE TRIGGER update_bugs_updated_at
        BEFORE UPDATE ON public.bugs
        FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Updated_at triggers created successfully")
    except Exception as e:
        print(f"Error creating triggers: {e}")

def setup_storage(supabase: Client):
    """Setup storage buckets and policies"""
    print("Setting up storage...")
    
    sql = """
    -- Create storage bucket for bug attachments
    INSERT INTO storage.buckets (id, name, public)
    VALUES ('bug-attachments', 'bug-attachments', false)
    ON CONFLICT (id) DO NOTHING;

    -- Create storage policies
    CREATE POLICY "Authenticated users can view attachments" ON storage.objects
        FOR SELECT USING (
            bucket_id = 'bug-attachments' AND
            auth.role() = 'authenticated'
        );

    CREATE POLICY "Authenticated users can upload attachments" ON storage.objects
        FOR INSERT WITH CHECK (
            bucket_id = 'bug-attachments' AND
            auth.role() = 'authenticated'
        );

    CREATE POLICY "Users can update own attachments" ON storage.objects
        FOR UPDATE USING (
            bucket_id = 'bug-attachments' AND
            owner = auth.uid()
        );

    CREATE POLICY "Users can delete own attachments" ON storage.objects
        FOR DELETE USING (
            bucket_id = 'bug-attachments' AND
            owner = auth.uid()
        );
    """
    
    try:
        supabase.postgrest.rpc('run_sql', {'sql': sql}).execute()
        print("✓ Storage setup completed successfully")
    except Exception as e:
        print(f"Error setting up storage: {e}")

def main():
    """Main setup function"""
    print("🚀 Setting up Supabase database for Bug Tracking Application")
    print("=" * 60)
    
    # Get Supabase client
    supabase = get_supabase_client()
    if not supabase:
        sys.exit(1)
    
    try:
        # Create all tables and policies
        create_users_table(supabase)
        create_projects_table(supabase)
        create_bugs_table(supabase)
        create_comments_table(supabase)
        create_notifications_table(supabase)
        create_audit_logs_table(supabase)
        create_updated_at_trigger(supabase)
        setup_storage(supabase)
        
        print("\n" + "=" * 60)
        print("✅ Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Verify all tables are created in your Supabase dashboard")
        print("2. Test the authentication flow")
        print("3. Run the FastAPI application")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
