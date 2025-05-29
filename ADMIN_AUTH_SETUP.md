# Admin Authentication Setup

This document describes the simple password protection system for the admin section.

## Overview

The admin section (`/admin/*`) is now protected with a simple password authentication system. This is a temporary solution that will be replaced with a proper authentication system later.

## How it works

1. **Middleware Protection**: All `/admin/*` routes are protected by Next.js middleware
2. **Login Page**: Users are redirected to `/admin/login` if not authenticated
3. **Session Cookie**: Authentication is maintained via an HTTP-only cookie
4. **Logout**: Users can logout via the logout button in the admin header

## Configuration

### Environment Variable

Set the admin password using the `ADMIN_PASSWORD` environment variable:

```bash
# In .env.local (create this file in the PromiseTracker directory)
ADMIN_PASSWORD=your_secure_password_here
```

If no environment variable is set, the default password is `admin123`.

### For Development

1. Create a `.env.local` file in the `PromiseTracker` directory
2. Add the line: `ADMIN_PASSWORD=your_password_here`
3. Restart your development server

### For Production

Set the `ADMIN_PASSWORD` environment variable in your deployment environment (Cloud Run, Vercel, etc.).

## Usage

1. Navigate to `/admin` (or any admin route)
2. You'll be redirected to `/admin/login`
3. Enter the admin password
4. You'll be redirected to the admin dashboard
5. Use the "Logout" button in the header to sign out

## Security Notes

- The password is stored in plain text in environment variables (temporary solution)
- Sessions last for 7 days
- Cookies are HTTP-only and secure in production
- This is NOT suitable for production use with multiple users

## Future Improvements

This simple system should be replaced with:
- Proper user authentication (Firebase Auth, Auth0, etc.)
- Role-based access control
- Password hashing
- Multi-factor authentication
- Audit logging

## Files Modified

- `middleware.ts` - Route protection
- `app/admin/login/page.tsx` - Login page
- `app/admin/login/layout.tsx` - Login layout
- `app/api/admin/auth/route.ts` - Authentication API
- `app/admin/layout.tsx` - Admin layout with logout 