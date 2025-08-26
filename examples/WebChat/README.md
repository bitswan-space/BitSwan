# WebChat - Interactive Web-Based Chat Interface for BSPump

WebChat is a component of BSPump that provides an interactive web-based chat interface with real-time communication, form handling, and dynamic flow management.

## 📋 Prerequisites

- Python 3.8+
- installed all requirements
- **bitswan**: https://github.com/bitswan-space/bitswan
- **bitswan workspace**: https://github.com/bitswan-space/bitswan-automation-server

## 🛠️ Installation

The WebChat components are included with BSPump. Ensure you have the required dependencies:

```bash
uv pip install -e ".[dev]"
```

## ⚙️ Running of the application

You have **2 options** how to run the app:

### 🚀 Option 1: Via bitswan notebook cli

1. **Set Environment Variable** - Create the env variable either in `.env` file or in bash:
   ```bash
   export JWT_SECRET="your-secret-key-here"
   ```

2. **Run the Notebook**:
   ```bash
   bitswan notebook examples/WebChat/main.ipynb
   ```

### 🌐 Option 2: Deploy from editor

1. **Follow Bitswan Workspace Steps** - Complete the setup from: https://github.com/bitswan-space/bitswan-automation-server

2. **Create Pipeline Configuration** - Create a `pipelines.conf` file with this structure:
   ```ini
   [deployment]
   pre=bitswan/pipeline-runtime-environment:latest
   expose=true

   [pipeline:WebChatPipeline:WebChatSource]
   JWT_SECRET=your-secret-key-here
   ```

3. **Deploy** - Then deploy from editor via bitswan extension.

## 🚀 Quick Start

The example structure can be found in `examples/WebChat/main.ipynb`

## 📝 Form Field Types

### Text Input Fields

```python
# Basic text field
TextField("username", display="Username", required=True)

# Hidden field (not visible to user)
TextField("session_id", hidden=True, default="abc123")

# Read-only field
TextField("user_id", readonly=True, default="user_001")
```

### Numeric Fields

```python
# Integer field
IntField("age", display="Age", required=True, default=18)

# Float field
FloatField("price", display="Price", required=True, default=0.0)
```

### Choice Fields

```python
# Dropdown selection
ChoiceField("category", choices=["A", "B", "C"], display="Category", required=True)

# With default selection
ChoiceField("status", choices=["Active", "Inactive"], default="Active")
```

### Boolean Fields

```python
# Checkbox
CheckboxField("agreement", display="I agree to terms", required=True)
```

### Date Fields

```python
# Date picker
DateField("birth_date", display="Birth Date", required=True)
```

### File Fields

```python
# File upload
FileField("document", display="Upload Document", required=True)

# Multiple files (if needed)
FileField("images", display="Upload Images", required=False)
```

### JSON Fields

```python
# Raw JSON input
RawJSONField("config", display="Configuration JSON", required=False, default="{}")
```

## 🔄 Flow Management

### Creating Flows

```python
chat = create_webchat_flow("dynamic_flow")
```

**Note**: Everything under this function call until another `create_webchat_flow` call will be added to the `dynamic_flow` function.

### Running Flows

```python
# Run a first flow
await run_flow("first flow")

# Or run a flow from another flow
await chat.run_flow("other_flow_name")

# Run flows conditionally
if condition:
    await chat.run_flow("flow_a")
else:
    await chat.run_flow("flow_b")
```

### Flow Response

```python
await chat.tell_user("Starting parent flow...")
await chat.run_flow("child_flow")
await chat.tell_user("Parent flow completed!")

child_flow = create_webchat_flow("child_flow")
child_flow.tell_user("Child flow executing...")
```

### Styling Responses

```python
# Send HTML content
await chat.tell_user("<strong>Bold message</strong>", is_html=True)

# Send plain text
await chat.tell_user("Plain text message", is_html=False)
```

---

**Happy Chatting! 🎉**
