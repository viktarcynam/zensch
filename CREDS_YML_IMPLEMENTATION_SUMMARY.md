# creds.yml Implementation - Complete Solution

## ✅ **ANSWER: YES, the code now checks for tokens.json AND creds.yml**

The server and startup scripts have been enhanced to automatically detect and use credentials from `creds.yml` along with existing `tokens.json` files, providing seamless startup while maintaining the standard schwabdev tokens format.

## **How It Works**

### **Credential Priority Order**
1. **Environment Variables** (highest priority)
   - `SCHWAB_APP_KEY`, `SCHWAB_APP_SECRET`, `SCHWAB_CALLBACK_URL`, `SCHWAB_TOKENS_FILE`
   
2. **creds.yml File** (second priority)
   - Contains app_key, app_secret, callback_url, token_path
   
3. **Manual Entry** (fallback)
   - Interactive credential entry via start_server.py

### **File Structure**
```
project/
├── creds.yml          # Your credentials (add to .gitignore)
├── tokens.json        # Standard schwabdev tokens (unchanged format)
├── server.py          # Direct server startup
└── start_server.py    # Interactive startup
```

## **creds.yml Format**

```yaml
app_key: "your_32_character_app_key_here_123"
app_secret: "your_16_char_key1"
callback_url: "https://127.0.0.1:8182"
token_path: "tokens.json"
```

**Important Notes:**
- Values must be quoted strings (YAML requirement)
- app_key must be exactly 32 characters
- app_secret must be exactly 16 characters
- callback_url must start with "https"
- token_path specifies where schwabdev stores tokens

## **Enhanced Components**

### **1. CredsManager (`creds_manager.py`)**
```python
class CredsManager:
    def load_credentials(self) -> Optional[dict]
    def get_credentials(self) -> Tuple[str, str, str, str]
    def has_valid_credentials(self) -> bool
    def create_sample_creds_file(self)
```

**Features:**
- ✅ YAML parsing with validation
- ✅ Credential format validation (32/16 char lengths)
- ✅ HTTPS URL validation
- ✅ Sample file generation

### **2. Enhanced Config (`config.py`)**
```python
class Config:
    def __init__(self):
        # Priority: Environment → creds.yml → defaults
        self.creds_manager = CredsManager()
        # Load credentials from creds.yml if env vars not set
```

**Features:**
- ✅ Automatic creds.yml loading
- ✅ Environment variable override
- ✅ Seamless integration with existing code

### **3. Standard tokens.json Format (Unchanged)**
```json
{
    "access_token_issued": "2025-08-07T20:00:00.000000+00:00",
    "refresh_token_issued": "2025-08-07T20:00:00.000000+00:00",
    "token_dictionary": {
        "access_token": "actual_access_token",
        "refresh_token": "actual_refresh_token",
        "id_token": "actual_id_token"
    }
}
```

**Benefits:**
- ✅ Standard schwabdev format preserved
- ✅ No breaking changes to existing tokens
- ✅ Compatible with all schwabdev operations

## **Startup Scenarios**

### **Scenario 1: Environment Variables Set**
```bash
export SCHWAB_APP_KEY="your_key"
export SCHWAB_APP_SECRET="your_secret"
python server.py
# Output: "Initializing server with environment credentials..."
```

### **Scenario 2: creds.yml + tokens.json Exist**
```bash
python server.py
# Output: "Valid tokens and stored credentials found - initializing server..."
# Uses credentials from creds.yml + tokens from tokens.json
```

### **Scenario 3: Only creds.yml Exists (First Time)**
```bash
python start_server.py
# Choose option 3 (Auto-detect)
# Uses creds.yml credentials → Authenticates → Creates tokens.json
```

### **Scenario 4: No Credentials**
```bash
python server.py
# Output: "No credentials or valid tokens found. Server starting without credentials."
```

## **Test Results**

### **Configuration Test**
```bash
python -c "from config import config; print(f'App key: {config.app_key}'); print(f'Can start with tokens: {config.can_start_with_tokens()}')"
```
**Output:**
```
App key: 12345678901234567890123456789012
Can start with tokens: True
```

### **Comprehensive Test Suite**
```bash
python test_creds_yml.py
```
**Results:**
- ✅ creds.yml loading and validation
- ✅ Config integration
- ✅ Standard tokens.json compatibility
- ✅ Invalid credential handling
- ✅ Sample file generation

### **Server Startup Test**
```bash
python server.py
```
**Output:**
```
INFO - Valid tokens and stored credentials found - initializing server...
INFO - Initializing Schwab API services...
INFO - Authenticating with Schwab API...
```

## **Production Workflow**

### **Development Setup**
1. **Create creds.yml**:
   ```bash
   cp creds.yml.sample creds.yml
   # Edit creds.yml with your credentials
   ```

2. **First Authentication**:
   ```bash
   python start_server.py
   # Choose option 3 → Authenticate → tokens.json created
   ```

3. **Subsequent Runs**:
   ```bash
   python server.py
   # Automatic startup using creds.yml + tokens.json
   ```

### **Production Deployment**
1. **Include creds.yml** in deployment package
2. **Authenticate once** to create tokens.json
3. **Server restarts automatically** using stored credentials + tokens
4. **No manual intervention** required for restarts

### **Security Best Practices**
```bash
# Add to .gitignore
echo "creds.yml" >> .gitignore

# Set restrictive permissions
chmod 600 creds.yml

# Use environment variables in CI/CD
export SCHWAB_APP_KEY="$PROD_APP_KEY"
export SCHWAB_APP_SECRET="$PROD_APP_SECRET"
```

## **Benefits Summary**

### **For schwabdev Compatibility**
- ✅ **Meets Requirements**: Provides app_key/app_secret for all operations
- ✅ **Token Refresh**: Credentials available for automatic token refresh
- ✅ **Standard Format**: tokens.json remains unchanged
- ✅ **Full API Support**: All schwabdev features work normally

### **For Development**
- ✅ **Simple Configuration**: Single YAML file for credentials
- ✅ **No Encryption Complexity**: Plain YAML with file permissions
- ✅ **Environment Override**: Easy testing with different credentials
- ✅ **Sample Files**: Clear documentation and examples

### **For Production**
- ✅ **Container Ready**: Include creds.yml in container image
- ✅ **Automatic Startup**: No manual credential entry needed
- ✅ **High Availability**: Servers restart automatically after crashes
- ✅ **CI/CD Compatible**: Environment variables override file credentials

### **For Security**
- ✅ **File Permissions**: 600 permissions on creds.yml
- ✅ **Git Ignore**: Credentials not committed to repository
- ✅ **Environment Priority**: Production can override with env vars
- ✅ **Validation**: Input validation prevents common errors

## **Migration Guide**

### **From Environment Variables Only**
- ✅ **No Changes Required**: Environment variables still take priority
- ✅ **Optional Enhancement**: Add creds.yml for convenience

### **From Manual Entry**
- ✅ **Create creds.yml**: One-time setup eliminates manual entry
- ✅ **Backward Compatible**: Manual entry still available as fallback

### **From Enhanced Tokens (Previous Solution)**
- ✅ **Simplified Approach**: No encryption complexity
- ✅ **Standard Format**: tokens.json returns to schwabdev standard
- ✅ **Easy Migration**: Copy credentials to creds.yml

## **Error Handling**

### **Invalid creds.yml**
```
Error loading creds.yml: app_key must be 32 characters long
App key: None
Can start with tokens: False
```

### **Missing creds.yml**
```
App key: None
Can start with tokens: False
# Falls back to manual entry or no-credentials mode
```

### **YAML Format Errors**
```
Error parsing creds.yml: while parsing a block mapping...
# Clear error messages guide user to fix format
```

## **Real-World Usage Examples**

### **Docker Deployment**
```dockerfile
COPY creds.yml /app/
RUN chmod 600 /app/creds.yml
CMD ["python", "server.py"]
```

### **Kubernetes Secret**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: schwab-creds
data:
  creds.yml: <base64-encoded-creds-yml>
```

### **CI/CD Pipeline**
```bash
# Use environment variables in CI
export SCHWAB_APP_KEY="$CI_APP_KEY"
export SCHWAB_APP_SECRET="$CI_APP_SECRET"
python server.py  # Uses env vars, ignores creds.yml
```

---

**The implementation successfully addresses the schwabdev credential requirements while providing a clean, maintainable solution that preserves the standard tokens.json format and enables seamless automatic startup.**