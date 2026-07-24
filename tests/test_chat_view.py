from spidermapp.gui.chat_view import _ws_url


def test_ws_url_converts_http_to_ws():
    assert _ws_url("http://127.0.0.1:8000", "general", "tok") == "ws://127.0.0.1:8000/ws/chat/general?token=tok"


def test_ws_url_converts_https_to_wss():
    assert _ws_url("https://pidge.example.com", "team", "tok2") == "wss://pidge.example.com/ws/chat/team?token=tok2"


def test_ws_url_strips_trailing_slash():
    assert _ws_url("http://127.0.0.1:8000/", "general", "tok") == "ws://127.0.0.1:8000/ws/chat/general?token=tok"
