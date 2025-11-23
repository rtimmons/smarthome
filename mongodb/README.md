# MongoDB Add-on

MongoDB Community Edition 8.x database server for Home Assistant add-ons.

## Features

- **MongoDB Community Edition 8.x** - Latest major version with full-text and vector search
- **Persistent storage** - Data stored in `/data` and included in Home Assistant backups
- **Network accessible** - Available to other add-ons via `mongodb:27017`
- **Local development** - Runs via Homebrew on macOS for local testing

## Installation & Deployment

### Home Assistant Deployment

Build and deploy the add-on to Home Assistant:

```bash
# From project root or mongodb directory
just deploy mongodb

# Or from mongodb directory
just deploy
```

### Local Development (macOS)

Setup and run MongoDB locally:

```bash
cd mongodb

# Install MongoDB via Homebrew (one-time setup)
just setup

# Start MongoDB locally on port 27017
just start
```

The local MongoDB instance:
- Listens on `localhost:27017`
- Stores data in `mongodb/data/` (gitignored)
- Connection string: `mongodb://localhost:27017/`

## Configuration

### Home Assistant Options

- `mongodb_version`: MongoDB major version (default: "8")

### Default Settings

- **Port**: 27017
- **Initial database**: smarthome
- **Data directory**: `/data/db` (mapped to add-on data storage)
- **Bind address**: All interfaces (0.0.0.0 in container, localhost in local dev)

## Usage from Other Add-ons

Other Home Assistant add-ons can connect to MongoDB using:

**Connection string:**
```
mongodb://mongodb:27017/
```

**Example environment variable in addon.yaml:**
```yaml
run_env:
  - env: MONGODB_URL
    from_option: mongodb_url
    default: "mongodb://mongodb:27017/smarthome"
```

The connection string will automatically be converted to `mongodb://localhost:27017/smarthome` during local development.

## Data Persistence & Backups

- **Container**: Data is stored in `/data/db` which is mapped to the add-on's data directory
- **Home Assistant**: Automatically includes MongoDB data in backups via the `map: data` configuration
- **Local dev**: Data is stored in `mongodb/data/` directory (not committed to git)

## MongoDB Version

This add-on uses **MongoDB Community Edition 8.x**, the latest major version that includes:

- Full-text search capabilities
- Vector search support
- Source-available under Server Side Public License (SSPL)

To verify the MongoDB version in your container:

```bash
# Connect to running add-on
docker exec -it addon_local_mongodb mongosh --eval "db.version()"
```

## Connecting to MongoDB

### From Home Assistant host

```bash
# Using mongosh CLI
mongosh mongodb://homeassistant.local:27017/

# List databases
mongosh mongodb://homeassistant.local:27017/ --eval "show dbs"
```

### From local development

```bash
# Using mongosh CLI
mongosh mongodb://localhost:27017/

# Or via MongoDB Compass GUI
# Connection string: mongodb://localhost:27017/
```

## Troubleshooting

### Expected Startup Warnings

When running `just start`, you'll see several warnings that are **normal and expected**:

1. **"Access control is not enabled"** (W 22120)
   - ✅ Expected for local dev and internal Home Assistant use
   - MongoDB runs on an isolated network accessible only to other add-ons

2. **"Soft rlimits for open file descriptors too low"** (W 22184)
   - ✅ Normal macOS behavior (256 vs recommended 64000)
   - Won't affect performance unless you have extremely high load
   - Optional fix: Add `ulimit -n 65536` to your shell profile

3. **"Use of deprecated server parameter name"** (W 636300, W 23803)
   - ✅ Informational only - MongoDB's internal diagnostics
   - No impact on functionality

**Success indicator:** Look for this line:
```
"msg":"Waiting for connections","attr":{"port":27017,"ssl":"off"}
```

### Local Development Issues

If `just start` fails:

1. Ensure Homebrew is installed
2. Run `just setup` to install MongoDB
3. Check that port 27017 is not already in use: `lsof -i :27017`
4. Verify MongoDB was installed: `which mongod`

### Home Assistant Issues

Check add-on logs:
```bash
ha addons logs local_mongodb
```

Verify MongoDB is accessible from other add-ons:
```bash
# From another add-on container
mongosh mongodb://mongodb:27017/ --eval "db.adminCommand({ping: 1})"
```

## Architecture Notes

This add-on uses a **custom Dockerfile** approach (not the standard Node.js/Python template) because MongoDB is a standalone database service. The build system has been enhanced to support custom Dockerfiles when `custom_dockerfile: true` is set in `addon.yaml`.
