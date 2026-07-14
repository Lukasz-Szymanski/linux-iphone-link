import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Dodajemy katalog główny do ścieżki, żeby można było zaimportować ancs_listener
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ancs_listener import notification_handler

def test_notification_handler_success(capsys):
    """Testuje czy handler poprawnie przetwarza i wyświetla surowe pakiety bajtów."""
    # Symulujemy przykładowy pakiet powiadomienia ANCS (8 bajtów)
    # EventID: 0 (Added), EventFlags: 1 (Silent), CategoryID: 4 (Social), Count: 1, UID: 0x12345678
    sample_data = bytearray([0x00, 0x01, 0x04, 0x01, 0x78, 0x56, 0x34, 0x12])
    
    mock_sender = MagicMock()
    
    # Przechwytujemy wyjście konsoli (rich)
    with patch('ancs_listener.console.print') as mock_print:
        notification_handler(mock_sender, sample_data)
        
        # Sprawdzamy, czy console.print zostało wywołane dwa razy
        assert mock_print.call_count == 2
        
        # Sprawdzamy treść pierwszego wywołania (hex)
        first_call_args = mock_print.call_args_list[0][0][0]
        assert "00 01 04 01 78 56 34 12" in first_call_args
        
        # Sprawdzamy treść drugiego wywołania (decymalne)
        second_call_args = mock_print.call_args_list[1][0][0]
        assert "Raw bytes: [0, 1, 4, 1, 120, 86, 52, 18]" in second_call_args
