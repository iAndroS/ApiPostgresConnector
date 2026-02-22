"""Tests for config module."""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEncryptDecrypt:
    """Tests for encryption/decryption functions."""
    
    @patch('src.config.CRYPTO_AVAILABLE', False)
    def test_encrypt_no_crypto(self):
        """Test encryption when cryptography not available."""
        from src.config import encrypt_password, decrypt_password
        
        result = encrypt_password("testpass")
        assert result == "testpass"
        
        result = decrypt_password("testpass")
        assert result == "testpass"
    
    @patch('src.config.CRYPTO_AVAILABLE', True)
    @patch('src.config.get_fernet')
    def test_encrypt_decrypt(self, mock_get_fernet):
        """Test encryption and decryption."""
        # Create mock Fernet
        import base64
        mock_fernet = MagicMock()
        
        # The encrypt function encrypts and then base64 encodes
        # So mock.encrypt should return the original password encoded
        # and decrypt should decode from base64 and return original
        original_password = "mypassword"
        encrypted_bytes = original_password.encode()
        mock_fernet.encrypt.return_value = encrypted_bytes
        mock_fernet.decrypt.return_value = encrypted_bytes
        mock_get_fernet.return_value = mock_fernet
        
        from src.config import encrypt_password, decrypt_password
        
        # Test encryption
        encrypted = encrypt_password("mypassword")
        assert encrypted != "mypassword"  # Should be different
        
        # Test decryption  
        decrypted = decrypt_password(encrypted)
        assert decrypted == "mypassword"
    
    def test_empty_password(self):
        """Test encryption with empty password."""
        from src.config import encrypt_password, decrypt_password
        
        assert encrypt_password("") == ""
        assert decrypt_password("") == ""


class TestConfig:
    """Tests for Config class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        from src.config import Config
        
        with patch.object(Config, 'load'):
            config = Config()
            config._config = config._get_default_config()
            
            assert config.database['host'] == 'localhost'
            assert config.database['port'] == 5432
            assert config.api['host'] == '127.0.0.1'
            assert config.api['port'] == 5000
    
    def test_update_database(self):
        """Test updating database config."""
        from src.config import Config
        
        with patch.object(Config, 'load'):
            config = Config()
            config._config = config._get_default_config()
            
            config.update_database(host='newhost', port=5433)
            
            assert config.database['host'] == 'newhost'
            assert config.database['port'] == 5433
    
    def test_update_api(self):
        """Test updating API config."""
        from src.config import Config
        
        with patch.object(Config, 'load'):
            config = Config()
            config._config = config._get_default_config()
            
            config.update_api(port=5001, debug=True)
            
            assert config.api['port'] == 5001
            assert config.api['debug'] is True
    
    def test_update_gui(self):
        """Test updating GUI config."""
        from src.config import Config
        
        with patch.object(Config, 'load'):
            config = Config()
            config._config = config._get_default_config()
            
            config.update_gui(theme='light', width=800)
            
            assert config.gui['theme'] == 'light'
            assert config.gui['width'] == 800
    
    @patch('src.config.get_fernet')
    def test_save_with_encryption(self, mock_get_fernet):
        """Test saving config encrypts password."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        try:
            from src.config import Config
            
            # Mock Fernet
            mock_fernet = MagicMock()
            mock_fernet.encrypt.return_value = b'encrypted'
            mock_get_fernet.return_value = mock_fernet
            
            with patch.object(Config, '__init__', lambda self: None):
                config = Config()
                config._config_path = Path(temp_path)
                config._config = {
                    'database': {'password': 'secret'},
                    'api': {},
                    'gui': {},
                    'app': {}
                }
                
                config.save()
                
                # Read and check the file
                with open(temp_path, 'r') as f:
                    saved = json.load(f)
                
                # Password should be encrypted (different from original)
                assert saved['database']['password'] != 'secret'
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
