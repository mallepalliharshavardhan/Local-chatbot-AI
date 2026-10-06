import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.aihawk_authenticator import AIHawkAuthenticator
from selenium.common.exceptions import NoSuchElementException, TimeoutException


@pytest.fixture
def mock_driver(mocker):
    """Fixture to mock the Selenium WebDriver."""
    return mocker.Mock()


@pytest.fixture
def authenticator(mock_driver):
    """Fixture to initialize AIHawkAuthenticator with a mocked driver."""
    return AIHawkAuthenticator(mock_driver)


def test_handle_login(mocker, authenticator):
    """Test handling the AIHawk login process."""
    mocker.patch.object(authenticator.driver, 'get')
    mocker.patch.object(authenticator, 'enter_credentials', return_value=True)
    mocker.patch.object(authenticator, 'is_logged_in')

    mocker.patch.object(authenticator.driver, 'current_url',
                        new='https://www.linkedin.com/login')

    assert authenticator.handle_login() is True

    authenticator.driver.get.assert_called_with(
        'https://www.linkedin.com/login')
    authenticator.enter_credentials.assert_called_once()
    authenticator.is_logged_in.assert_not_called()


def test_enter_credentials_success(mocker, authenticator):
    """Wait for the bot browser to reach LinkedIn's feed and verify access."""
    mocker.patch.object(WebDriverWait, 'until')
    mocker.patch.object(authenticator, 'is_logged_in', return_value=True)

    assert authenticator.enter_credentials() is True
    authenticator.is_logged_in.assert_called_once()

def test_enter_credentials_timeout_fails(mocker, authenticator):
    mocker.patch.object(WebDriverWait, 'until', side_effect=TimeoutException)

    assert authenticator.enter_credentials() is False

def test_handle_login_returns_false_when_not_authenticated(mocker, authenticator):
    mocker.patch.object(authenticator.driver, 'get')
    mocker.patch.object(authenticator.driver, 'current_url', new='https://www.linkedin.com/login')
    mocker.patch.object(authenticator, 'enter_credentials', return_value=False)

    assert authenticator.handle_login() is False

def test_is_logged_in_true(mocker, authenticator):
    """The authenticated feed route confirms login without relying on fragile UI selectors."""
    mocker.patch.object(authenticator.driver, 'get')
    mocker.patch.object(authenticator.driver, 'current_url', new='https://www.linkedin.com/feed/')
    mocker.patch.object(WebDriverWait, 'until', return_value=True)

    assert authenticator.is_logged_in() is True


def test_is_logged_in_false(mocker, authenticator):
    """A redirect to LinkedIn login means the bot is not authenticated."""
    mocker.patch.object(authenticator.driver, 'get')
    mocker.patch.object(authenticator.driver, 'current_url', new='https://www.linkedin.com/login')
    mocker.patch.object(WebDriverWait, 'until', return_value=True)

    assert authenticator.is_logged_in() is False


def test_handle_security_check_success(mocker, authenticator):
    """Test handling security check successfully."""
    mocker.patch.object(WebDriverWait, 'until', side_effect=[
        mocker.Mock(),  # Security checkpoint detection
        mocker.Mock()   # Security check completion
    ])

    authenticator.handle_security_check()

    # Verify WebDriverWait is called with EC.url_contains for both the challenge and feed
    WebDriverWait(authenticator.driver, 10).until.assert_any_call(mocker.ANY)
    WebDriverWait(authenticator.driver, 300).until.assert_any_call(mocker.ANY)


def test_handle_security_check_timeout(mocker, authenticator):
    """Test handling security check timeout."""
    mocker.patch.object(WebDriverWait, 'until', side_effect=TimeoutException)

    authenticator.handle_security_check()

    # Verify WebDriverWait is called with EC.url_contains for the challenge
    WebDriverWait(authenticator.driver, 10).until.assert_any_call(mocker.ANY)
