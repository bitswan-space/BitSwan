# BitSwan Secrets Management

## Overview

BitSwan uses environment files to manage secrets and sensitive configuration values. These secrets are made available as environment variables within pipelines and Jupyter notebooks.

## Setup

1. You will see a `secrets` directory in your VSCode Server workspace.
2. Create environment files in the secrets directory.
3. Configure secret groups in `pipelines.conf`.

## Usage Example

### 1. Create Environment File

Create a file in the secrets directory (e.g., `foo`):
```txt
FOO=foo
```

### 2. Configure Secret Groups

In `pipelines.conf`, add the secrets group:

```ini
[secrets]
groups=foo
```

You can give your pipelines access to secrets by providing a space separated list of secrets groups.

```ini
[secrets]
groups=foo bar
```

### 3. Accessing Secrets

- In pipelines: Environment variables (e.g., `$FOO`) will be automatically available.
- In Jupyter notebooks: Environment variables are set automatically after importing the `bspump` library.

## Notes

- Each env file in the secrets dir represents a secrets group
- Secret values are loaded as environment variables
- Jupyter integration happens automatically with bspump import
```
