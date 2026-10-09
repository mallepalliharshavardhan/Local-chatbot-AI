import httpx
import pytest

from src.llm.llm_manager import LoggerChatModel


class ProviderAuthenticationError(Exception):
    status_code = 401


@pytest.mark.parametrize(
    "error",
    [
        ProviderAuthenticationError("credential rejected"),
        httpx.HTTPStatusError(
            "credential rejected",
            request=httpx.Request("POST", "https://example.invalid"),
            response=httpx.Response(
                401,
                request=httpx.Request("POST", "https://example.invalid"),
            ),
        ),
    ],
)
def test_logger_chat_model_fails_fast_on_invalid_credentials(mocker, error):
    llm = mocker.Mock()
    llm.invoke.side_effect = error
    model = LoggerChatModel(llm)
    sleep = mocker.patch("src.llm.llm_manager.time.sleep")

    with pytest.raises(RuntimeError, match="HTTP 401"):
        model([])

    sleep.assert_not_called()
