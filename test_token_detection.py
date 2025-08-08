#!/usr/bin/env python3
"""
Test script to verify token detection functionality.
"""
import os
import shutil
from config import config

def test_token_detection():
    """Test the token detection functionality."""
    print("Testing Token Detection Functionality")
    print("=" * 50)
    
    # Save original tokens file path
    original_tokens_file = config.tokens_file
    
    try:
        # Test 1: No tokens file
        config.tokens_file = "nonexistent_tokens.json"
        print(f"\n1. Testing with no tokens file: {config.tokens_file}")
        print(f"   has_valid_tokens(): {config.has_valid_tokens()}")
        print(f"   can_start_with_tokens(): {config.can_start_with_tokens()}")
        
        # Test 2: Valid tokens file
        config.tokens_file = "test_tokens.json"
        print(f"\n2. Testing with valid tokens file: {config.tokens_file}")
        print(f"   has_valid_tokens(): {config.has_valid_tokens()}")
        print(f"   can_start_with_tokens(): {config.can_start_with_tokens()}")
        
        # Test 3: Environment credentials
        print(f"\n3. Testing environment credentials:")
        print(f"   SCHWAB_APP_KEY: {'SET' if config.app_key else 'NOT SET'}")
        print(f"   SCHWAB_APP_SECRET: {'SET' if config.app_secret else 'NOT SET'}")
        print(f"   is_configured(): {config.is_configured()}")
        
        # Test 4: Startup decision logic
        print(f"\n4. Server startup decision:")
        if config.is_configured():
            print("   → Use environment credentials")
        elif config.can_start_with_tokens():
            print("   → Use existing tokens")
        else:
            print("   → Start without credentials")
            
        # Test 5: Create expired tokens file
        expired_tokens_content = """{
    "access_token_issued": "2020-01-01T00:00:00.000000+00:00",
    "refresh_token_issued": "2020-01-01T00:00:00.000000+00:00",
    "token_dictionary": {
        "access_token": "expired_access_token",
        "refresh_token": "expired_refresh_token",
        "id_token": "expired_id_token"
    }
}"""
        
        with open("expired_tokens.json", "w") as f:
            f.write(expired_tokens_content)
            
        config.tokens_file = "expired_tokens.json"
        print(f"\n5. Testing with expired tokens file: {config.tokens_file}")
        print(f"   has_valid_tokens(): {config.has_valid_tokens()}")
        print(f"   can_start_with_tokens(): {config.can_start_with_tokens()}")
        
        # Cleanup
        os.remove("expired_tokens.json")
        
    finally:
        # Restore original tokens file path
        config.tokens_file = original_tokens_file
    
    print(f"\n" + "=" * 50)
    print("Token Detection Test Complete!")

if __name__ == "__main__":
    test_token_detection()