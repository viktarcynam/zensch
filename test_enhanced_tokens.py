#!/usr/bin/env python3
"""
Test script to demonstrate enhanced token management with stored credentials.
"""
import os
import json
from enhanced_tokens import EnhancedTokensManager
from config import config

def test_enhanced_tokens():
    """Test the enhanced token management functionality."""
    print("Testing Enhanced Token Management")
    print("=" * 50)
    
    # Test credentials
    test_app_key = "12345678901234567890123456789012"  # 32 chars
    test_app_secret = "1234567890123456"  # 16 chars  
    test_callback_url = "https://127.0.0.1:8182"
    
    # Clean up any existing test files
    test_files = ["test_enhanced_tokens.json", "test_enhanced_tokens.json.key"]
    for file in test_files:
        if os.path.exists(file):
            os.remove(file)
    
    try:
        # Test 1: Create enhanced tokens manager
        print("\n1. Creating enhanced tokens manager...")
        enhanced_tokens = EnhancedTokensManager("test_enhanced_tokens.json")
        print(f"   has_stored_credentials(): {enhanced_tokens.has_stored_credentials()}")
        
        # Test 2: Create basic tokens file (like schwabdev would create)
        print("\n2. Creating basic tokens file...")
        basic_tokens = {
            "access_token_issued": "2025-08-07T20:00:00.000000+00:00",
            "refresh_token_issued": "2025-08-07T20:00:00.000000+00:00",
            "token_dictionary": {
                "access_token": "test_access_token_12345",
                "refresh_token": "test_refresh_token_67890",
                "id_token": "test_id_token_abcdef"
            }
        }
        
        with open("test_enhanced_tokens.json", "w") as f:
            json.dump(basic_tokens, f, indent=4)
        print("   Basic tokens file created")
        
        # Test 3: Enhance tokens file with credentials
        print("\n3. Enhancing tokens file with encrypted credentials...")
        enhanced_tokens.enhance_tokens_file(test_app_key, test_app_secret, test_callback_url)
        print(f"   has_stored_credentials(): {enhanced_tokens.has_stored_credentials()}")
        
        # Test 4: Retrieve stored credentials
        print("\n4. Retrieving stored credentials...")
        stored_creds = enhanced_tokens.get_stored_credentials()
        if stored_creds:
            stored_key, stored_secret, stored_callback = stored_creds
            print(f"   App Key: {stored_key[:8]}...{stored_key[-8:]}")
            print(f"   App Secret: {stored_secret[:4]}...{stored_secret[-4:]}")
            print(f"   Callback URL: {stored_callback}")
            print(f"   Credentials match: {stored_key == test_app_key and stored_secret == test_app_secret}")
        else:
            print("   No credentials retrieved!")
        
        # Test 5: Check enhanced tokens file structure
        print("\n5. Enhanced tokens file structure:")
        with open("test_enhanced_tokens.json", "r") as f:
            enhanced_data = json.load(f)
        
        print(f"   Has token_dictionary: {'token_dictionary' in enhanced_data}")
        print(f"   Has stored_credentials: {'stored_credentials' in enhanced_data}")
        print(f"   Has enhanced_version: {'enhanced_version' in enhanced_data}")
        print(f"   Encryption key file exists: {os.path.exists('test_enhanced_tokens.json.key')}")
        
        # Test 6: Test config integration
        print("\n6. Testing config integration...")
        original_tokens_file = config.tokens_file
        config.tokens_file = "test_enhanced_tokens.json"
        
        print(f"   config.has_valid_tokens(): {config.has_valid_tokens()}")
        print(f"   config.can_start_with_tokens(): {config.can_start_with_tokens()}")
        
        stored_config_creds = config.get_stored_credentials()
        if stored_config_creds and stored_config_creds[0]:
            print(f"   Config can retrieve credentials: YES")
        else:
            print(f"   Config can retrieve credentials: NO")
        
        config.tokens_file = original_tokens_file
        
        # Test 7: Security verification
        print("\n7. Security verification...")
        with open("test_enhanced_tokens.json", "r") as f:
            file_content = f.read()
        
        credentials_visible = (test_app_key in file_content or test_app_secret in file_content)
        print(f"   Credentials visible in file: {credentials_visible}")
        print(f"   File contains encrypted data: {'encrypted_credentials' in file_content}")
        
        # Test 8: Remove credentials
        print("\n8. Testing credential removal...")
        enhanced_tokens.remove_stored_credentials()
        print(f"   has_stored_credentials() after removal: {enhanced_tokens.has_stored_credentials()}")
        print(f"   Key file exists after removal: {os.path.exists('test_enhanced_tokens.json.key')}")
        
    finally:
        # Cleanup
        for file in test_files:
            if os.path.exists(file):
                os.remove(file)
    
    print(f"\n" + "=" * 50)
    print("Enhanced Token Management Test Complete!")

def demonstrate_workflow():
    """Demonstrate the complete workflow."""
    print("\n" + "=" * 60)
    print("ENHANCED WORKFLOW DEMONSTRATION")
    print("=" * 60)
    
    print("\n🔄 **Complete Authentication Workflow:**")
    print("1. First time: User provides credentials → tokens.json created")
    print("2. Enhancement: Credentials encrypted and stored in tokens.json")
    print("3. Future startups: Server uses stored credentials + tokens")
    print("4. Token refresh: schwabdev uses stored credentials automatically")
    print("5. No user interaction needed for subsequent startups")
    
    print("\n🔐 **Security Features:**")
    print("- Credentials encrypted with Fernet (AES 128)")
    print("- Separate encryption key file with restricted permissions")
    print("- No plaintext credentials in tokens file")
    print("- Key rotation possible by regenerating key file")
    
    print("\n🚀 **Startup Scenarios:**")
    print("Scenario A: Environment variables set")
    print("  → Use environment credentials (highest priority)")
    print("")
    print("Scenario B: Enhanced tokens.json exists")
    print("  → Use stored encrypted credentials + tokens")
    print("")
    print("Scenario C: Basic tokens.json only")
    print("  → Cannot start (schwabdev needs credentials)")
    print("")
    print("Scenario D: No credentials or tokens")
    print("  → Start in no-credentials mode")
    
    print("\n✅ **Benefits:**")
    print("- Seamless startup after first authentication")
    print("- Secure credential storage")
    print("- Compatible with schwabdev requirements")
    print("- No breaking changes to existing functionality")
    print("- Production-ready for containers and CI/CD")

if __name__ == "__main__":
    test_enhanced_tokens()
    demonstrate_workflow()