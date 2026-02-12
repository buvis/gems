from readerctl.adapters.response import AdapterResponse


class TestAdapterResponse:
    def test_ok_response(self):
        r = AdapterResponse(code=0, message="success")
        assert r.is_ok() is True
        assert r.is_nok() is False

    def test_error_response(self):
        r = AdapterResponse(code=401, message="unauthorized")
        assert r.is_ok() is False
        assert r.is_nok() is True

    def test_defaults(self):
        r = AdapterResponse()
        assert r.code == 0
        assert r.message == ""
        assert r.is_ok() is True

    def test_message_only(self):
        r = AdapterResponse(message="token valid")
        assert r.is_ok() is True
        assert r.message == "token valid"
