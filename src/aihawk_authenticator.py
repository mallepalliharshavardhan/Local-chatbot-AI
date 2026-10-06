from urllib.parse import urlparse

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from loguru import logger


class AIHawkAuthenticator:

    def __init__(self, driver=None):
        self.driver = driver
        logger.debug(f"AIHawkAuthenticator initialized with driver: {driver}")

    @staticmethod
    def _is_feed_url(url: str) -> bool:
        parsed_url = urlparse(url)
        return (
            parsed_url.scheme == "https"
            and parsed_url.netloc.lower() == "www.linkedin.com"
            and (parsed_url.path == "/feed" or parsed_url.path.startswith("/feed/"))
        )

    def start(self) -> bool:
        logger.info("Starting Chrome browser to log in to AIHawk.")
        if self.is_logged_in():
            logger.info("User is already logged in. Skipping login process.")
            return True
        else:
            logger.info("User is not logged in. Proceeding with login.")
            return self.handle_login()

    def handle_login(self) -> bool:
        logger.info("Navigating to the AIHawk login page...")
        self.driver.get("https://www.linkedin.com/login")
        if 'feed' in self.driver.current_url:
            logger.debug("User is already logged in.")
            return self.is_logged_in()
        return self.enter_credentials()


    def enter_credentials(self) -> bool:
        logger.info(
            "Sign in to LinkedIn in this bot-opened Chrome window and complete any verification. "
            "Waiting up to 5 minutes."
        )
        try:
            WebDriverWait(self.driver, 300).until(
                lambda driver: self._is_feed_url(driver.current_url)
            )
        except TimeoutException:
            logger.error("LinkedIn login was not confirmed within 5 minutes.")
            return False
        return self.is_logged_in()


    def handle_security_check(self):
        try:
            logger.debug("Handling security check...")
            WebDriverWait(self.driver, 10).until(
                EC.url_contains('https://www.linkedin.com/checkpoint/challengesV2/')
            )
            logger.warning("Security checkpoint detected. Please complete the challenge.")
            WebDriverWait(self.driver, 300).until(
                EC.url_contains('https://www.linkedin.com/feed/')
            )
            logger.info("Security check completed")
        except TimeoutException:
            logger.error("Security check not completed. Please try again later.")

    def is_logged_in(self):
        try:
            self.driver.get('https://www.linkedin.com/feed/')
            logger.debug("Checking if user is logged in...")
            WebDriverWait(self.driver, 10).until(
                lambda driver: self._is_feed_url(driver.current_url)
                or "linkedin.com/login" in driver.current_url
                or "linkedin.com/checkpoint/" in driver.current_url
            )
        except TimeoutException:
            logger.error("LinkedIn did not resolve to a feed or sign-in page.")
            return False

        if self._is_feed_url(self.driver.current_url):
            logger.info("LinkedIn feed route confirmed; login is active.")
            return True

        logger.info("LinkedIn redirected to login or checkpoint; login is not confirmed.")
        return False