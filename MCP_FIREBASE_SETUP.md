# Firebase MCP Server Setup Guide

## Overview
This guide explains how to set up and use the Firebase MCP (Model Context Protocol) server for managing Firestore operations in the Promise Tracker project.

## Prerequisites
- Node.js v20.0.0 or later (✅ currently using v22.16.0)
- Firebase CLI installed and authenticated (✅ completed)
- Firebase project configured (✅ promisetrackerapp)

## MCP Configuration


### For Cursor IDE
Add the Firebase MCP server to your Cursor MCP configuration:

```json
{
  "mcpServers": {
    "firebase": {
      "command": "npx",
      "args": ["-y", "firebase-tools@latest", "experimental:mcp"],
      "env": {
        "FIREBASE_PROJECT_ID": "promisetrackerapp"
      }
    }
  }
}
```

## Environment Variables
Make sure these environment variables are set in your development environment:

- `FIREBASE_PROJECT_ID=promisetrackerapp`
- `GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json`

## Firebase MCP Server Capabilities

The Firebase MCP server provides tools for:

1. **Firestore Operations**
   - Read documents and collections
   - Write/update documents
   - Query data with filters
   - Manage indexes

2. **Project Management**
   - List Firebase projects
   - Get project information
   - Manage project settings

3. **Security Rules**
   - Read current Firestore rules
   - Validate rules
   - Deploy rule changes

4. **Emulator Integration**
   - Start/stop emulators
   - Connect to local emulator instances

## Example Usage Patterns

### Reading Promise Data
```
Please use the Firebase MCP server to:
1. List all promises in the 'promises' collection
2. Show me promises for a specific department
3. Get the count of promises by status
```

### Querying Collections
```
Using the Firebase MCP server, query the promises collection to:
- Find all promises with status "In Progress"
- Get promises created in the last 30 days
- List promises by priority level
```

### Data Management
```
Help me use the Firebase MCP server to:
- Update a promise status
- Add new evidence to a promise
- Create a new department configuration
```

## Project-Specific Collections

Your Firestore database contains these main collections:
- `promises` - Political promises and commitments
- `department_configs` - Department configuration data
- `parliament_sessions` - Parliamentary session information
- `evidence` - Supporting evidence for promises

## Security Considerations

- The MCP server uses your authenticated Firebase CLI session
- All operations respect Firestore security rules
- Service account credentials are used for administrative operations
- Local emulator can be used for safe testing

## Troubleshooting

### Common Issues
1. **Node.js version mismatch**: Ensure Node.js v20+ is installed
2. **Authentication errors**: Run `firebase login --reauth`
3. **Project access**: Verify you have appropriate permissions
4. **MCP server not starting**: Check Firebase CLI installation

### Verification Commands
```bash
# Check Node.js version
node --version

# Verify Firebase login
firebase projects:list

# Test MCP server
npx -y firebase-tools@latest experimental:mcp --version
```

## Integration with Existing Scripts

The MCP server complements your existing Python scripts:
- Use MCP for interactive queries and exploration
- Use Python scripts for batch operations and automation
- Both can work with the same Firestore database

## Next Steps

1. Configure your MCP client with the provided configuration
2. Restart your MCP client (Cursor)
3. Test the connection by asking to list Firebase projects
4. Explore your Firestore collections using natural language queries

## Support

For Firebase MCP server issues:
- Check Firebase CLI documentation
- Use `firebase --help` for command reference
- Review Firebase console for project status 