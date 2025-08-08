#!/usr/bin/env python3
"""
Test script for creds.yml based credential management.
"""
import os
import json
import yaml
from creds_manager import CredsManager
from config import config

def test_creds_yml_functionality():
    """Test the creds.yml functionality."""
    print("Testing creds.yml Credential Management")
    print("=" * 50)
    
    # Test credentials
    test_app_key = "12345678901234567890123456789012"  # 32 chars
    test_app_secret = "1234567890123456"  # 16 chars  
    test_callback_url = "https://127.0.0.1:8182"
    test_token_path = "test_tokens.json"
    
    # Clean up any existing test files
    test_files = ["test_creds.yml", "test_tokens.json"]
    for file in test_files:
        if os.path.exists(file):
            os.remove(file)
    
    try:
        # Test 1: No creds.yml file
        print("\n1. Testing with no creds.yml file...")
        creds_manager = CredsManager("test_creds.yml")
        print(f"   has_valid_credentials(): {creds_manager.has_valid_credentials()}")
        print(f"   get_credentials(): {creds_manager.get_credentials()}")
        
        # Test 2: Create creds.yml file
        print("\n2. Creating creds.yml file...")
        test_creds = {
            'app_key': test_app_key,
            'app_secret': test_app_secret,
            'callback_url': test_callback_url,
            'token_path': test_token_path
        }
        
        with open("test_creds.yml", "w") as f:
            yaml.dump(test_creds, f, default_flow_style=False, indent=2)
        
        print("   creds.yml file created")
        
        # Test 3: Load credentials from file
        print("\n3. Loading credentials from creds.yml...")
        creds_manager = CredsManager("test_creds.yml")
        print(f"   has_valid_credentials(): {creds_manager.has_valid_credentials()}")
        
        app_key, app_secret, callback_url, token_path = creds_manager.get_credentials()
        print(f"   App Key: {app_key[:8]}...{app_key[-8:] if app_key else 'None'}")
        print(f"   App Secret: {app_secret[:4]}...{app_secret[-4:] if app_secret else 'None'}")
        print(f"   Callback URL: {callback_url}")
        print(f"   Token Path: {token_path}")
        
        # Test 4: Validate credentials
        print("\n4. Validating credentials...")
        loaded_creds = creds_manager.load_credentials()
        if loaded_creds:
            print(f"   All required keys present: {all(k in loaded_creds for k in ['app_key', 'app_secret', 'callback_url', 'token_path'])}")
            print(f"   App key length correct: {len(loaded_creds['app_key']) == 32}")
            print(f"   App secret length correct: {len(loaded_creds['app_secret']) == 16}")
            print(f"   Callback URL starts with https: {loaded_creds['callback_url'].startswith('https')}")
        
        # Test 5: Create standard schwabdev tokens.json
        print("\n5. Creating standard schwabdev tokens.json...")
        standard_tokens = {
            "access_token_issued": "2025-08-07T20:00:00.000000+00:00",
            "refresh_token_issued": "2025-08-07T20:00:00.000000+00:00",
            "token_dictionary": {
                "access_token": "test_access_token_12345",
                "refresh_token": "test_refresh_token_67890",
                "id_token": "test_id_token_abcdef"
            }
        }
        
        with open("test_tokens.json", "w") as f:
            json.dump(standard_tokens, f, indent=4)
        
        print("   Standard tokens.json created (schwabdev format)")
        
        # Test 6: Test config integration
        print("\n6. Testing config integration...")
        # Save original config values
        original_app_key = config.app_key
        original_app_secret = config.app_secret
        original_tokens_file = config.tokens_file
        
        # Create new config with test creds file
        from config import Config
        test_config = Config()
        test_config.creds_manager = CredsManager("test_creds.yml")
        
        # Simulate loading from creds.yml (no env vars)
        test_config.app_key = None
        test_config.app_secret = None
        
        # Load from creds.yml
        creds_app_key, creds_app_secret, creds_callback_url, creds_token_path = test_config.creds_manager.get_credentials()
        if creds_app_key and creds_app_secret:
            test_config.app_key = creds_app_key
            test_config.app_secret = creds_app_secret
            test_config.callback_url = creds_callback_url
            test_config.tokens_file = creds_token_path
        
        print(f"   Config loaded from creds.yml: {bool(test_config.app_key and test_config.app_secret)}")
        print(f"   Config tokens file: {test_config.tokens_file}")
        
        # Test token validation with custom tokens file
        test_config.tokens_file = "test_tokens.json"
        print(f"   has_valid_tokens(): {test_config.has_valid_tokens()}")
        print(f"   can_start_with_tokens(): {test_config.can_start_with_tokens()}")
        
        # Test 7: Invalid creds.yml file
        print("\n7. Testing invalid creds.yml file...")
        invalid_creds = {
            'app_key': 'too_short',  # Invalid length
            'app_secret': 'also_short',  # Invalid length
            'callback_url': 'http://invalid',  # Should be https
            'token_path': 'tokens.json'
        }
        
        with open("test_creds_invalid.yml", "w") as f:
            yaml.dump(invalid_creds, f, default_flow_style=False, indent=2)
        
        invalid_creds_manager = CredsManager("test_creds_invalid.yml")
        print(f"   Invalid creds has_valid_credentials(): {invalid_creds_manager.has_valid_credentials()}")
        
        # Cleanup invalid file
        os.remove("test_creds_invalid.yml")
        
        # Test 8: Sample file creation
        print("\n8. Testing sample file creation...")
        sample_creds_manager = CredsManager("test_sample_creds.yml")
        sample_creds_manager.create_sample_creds_file()
        
        sample_exists = os.path.exists("test_sample_creds.yml")
        print(f"   Sample file created: {sample_exists}")
        
        if sample_exists:
            with open("test_sample_creds.yml", "r") as f:
                sample_content = yaml.safe_load(f)
            print(f"   Sample has all required keys: {all(k in sample_content for k in ['app_key', 'app_secret', 'callback_url', 'token_path'])}")
            os.remove("test_sample_creds.yml")
        
    finally:
        # Cleanup
        for file in test_files + ["test_creds_invalid.yml", "test_sample_creds.yml"]:
            if os.path.exists(file):
                os.remove(file)
    
    print(f"\n" + "=" * 50)
    print("creds.yml Test Complete!")

def demonstrate_workflow():
    """Demonstrate the complete workflow with creds.yml."""
    print("\n" + "=" * 60)
    print("CREDS.YML WORKFLOW DEMONSTRATION")
    print("=" * 60)
    
    print("\n📁 **File Structure:**")
    print("├── creds.yml          # Your credentials (secure, .gitignore)")
    print("├── tokens.json        # schwabdev tokens (standard format)")
    print("├── server.py          # Server startup")
    print("└── start_server.py    # Interactive startup")
    
    print("\n🔄 **Startup Priority Order:**")
    print("1. Environment Variables (SCHWAB_APP_KEY, SCHWAB_APP_SECRET)")
    print("2. creds.yml file")
    print("3. Manual entry (start_server.py)")
    
    print("\n📝 **creds.yml Format:**")
    print("```yaml")
    print("app_key: your_32_character_app_key_here_123")
    print("app_secret: your_16_char_key1")
    print("callback_url: https://127.0.0.1:8182")
    print("token_path: tokens.json")
    print("```")
    
    print("\n🚀 **Usage Scenarios:**")
    print("")
    print("**First Time Setup:**")
    print("1. Copy creds.yml.sample to creds.yml")
    print("2. Edit creds.yml with your credentials")
    print("3. Run: python start_server.py")
    print("4. Authenticate once → tokens.json created")
    print("5. Future runs: python server.py (automatic)")
    
    print("\n**Production Deployment:**")
    print("1. Include creds.yml in deployment")
    print("2. Authenticate once to create tokens.json")
    print("3. Server restarts automatically using creds.yml + tokens.json")
    
    print("\n**Development Workflow:**")
    print("1. Add creds.yml to .gitignore")
    print("2. Each developer has their own creds.yml")
    print("3. Shared tokens.json.sample for reference")
    
    print("\n✅ **Benefits:**")
    print("- Standard schwabdev tokens.json format preserved")
    print("- Secure credential storage separate from tokens")
    print("- Simple YAML configuration")
    print("- Environment variable override support")
    print("- No encryption complexity")
    print("- Easy to understand and maintain")

if __name__ == "__main__":
    test_creds_yml_functionality()
    demonstrate_workflow()