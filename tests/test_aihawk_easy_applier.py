import pytest
from unittest import mock
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from src.aihawk_easy_applier import AIHawkEasyApplier, ApplicationSubmissionUnconfirmed


@pytest.fixture
def mock_driver():
    """Fixture to mock Selenium WebDriver."""
    return mock.Mock()


@pytest.fixture
def mock_gpt_answerer():
    """Fixture to mock GPT Answerer."""
    return mock.Mock()


@pytest.fixture
def mock_resume_generator_manager():
    """Fixture to mock Resume Generator Manager."""
    return mock.Mock()


@pytest.fixture
def easy_applier(mock_driver, mock_gpt_answerer, mock_resume_generator_manager):
    """Fixture to initialize AIHawkEasyApplier with mocks."""
    return AIHawkEasyApplier(
        driver=mock_driver,
        resume_dir="/path/to/resume",
        set_old_answers=[('Question 1', 'Answer 1', 'Type 1')],
        gpt_answerer=mock_gpt_answerer,
        resume_generator_manager=mock_resume_generator_manager
    )


def test_initialization(mocker, easy_applier):
    """Test that AIHawkEasyApplier is initialized correctly."""
    # Mock os.path.exists to return True
    mocker.patch('os.path.exists', return_value=True)

    easy_applier = AIHawkEasyApplier(
        driver=mocker.Mock(),
        resume_dir="/path/to/resume",
        set_old_answers=[('Question 1', 'Answer 1', 'Type 1')],
        gpt_answerer=mocker.Mock(),
        resume_generator_manager=mocker.Mock()
    )

    assert easy_applier.resume_path == "/path/to/resume"
    assert len(easy_applier.set_old_answers) == 1
    assert easy_applier.gpt_answerer is not None
    assert easy_applier.resume_generator_manager is not None


def test_apply_to_job_success(mocker, easy_applier):
    """Test successfully applying to a job."""
    mock_job = mock.Mock()

    # Mock job_apply so we don't actually try to apply
    mocker.patch.object(easy_applier, 'job_apply')

    easy_applier.apply_to_job(mock_job)
    easy_applier.job_apply.assert_called_once_with(mock_job)


def test_apply_to_job_failure(mocker, easy_applier):
    """Test failure while applying to a job."""
    mock_job = mock.Mock()
    mocker.patch.object(easy_applier, 'job_apply',
                        side_effect=Exception("Test error"))

    with pytest.raises(Exception, match="Test error"):
        easy_applier.apply_to_job(mock_job)

    easy_applier.job_apply.assert_called_once_with(mock_job)


def test_get_job_description_supports_current_linkedin_selector(mocker, easy_applier):
    description = mock.Mock()
    description.text = "Build and maintain frontend applications."
    mocker.patch.object(
        easy_applier.driver,
        'find_element',
        side_effect=NoSuchElementException,
    )
    mocker.patch.object(
        easy_applier.driver,
        'find_elements',
        side_effect=[[], [description]],
    )

    assert easy_applier._get_job_description() == description.text


def test_get_job_description_reads_semantic_about_the_job_section(mocker, easy_applier):
    heading = mocker.Mock()
    section = mocker.Mock()
    section.text = "About the job\nBuild and maintain frontend applications."
    heading.find_element.return_value = section
    mocker.patch.object(easy_applier.driver, 'find_element', side_effect=NoSuchElementException)
    mocker.patch.object(
        easy_applier.driver,
        'find_elements',
        side_effect=lambda by, selector: [heading] if by == "xpath" else [],
    )

    assert easy_applier._get_job_description() == "Build and maintain frontend applications."


def test_get_job_description_fails_safely_when_missing(mocker, easy_applier):
    mocker.patch.object(
        easy_applier.driver,
        'find_element',
        side_effect=NoSuchElementException,
    )
    mocker.patch.object(easy_applier.driver, 'find_elements', return_value=[])
    mocker.patch.object(easy_applier.driver, 'title', new="Job details")
    mocker.patch.object(
        easy_applier.driver,
        'current_url',
        new="https://www.linkedin.com/jobs/view/123",
    )

    with pytest.raises(RuntimeError, match="Job description not found"):
        easy_applier._get_job_description()


def test_wait_for_submission_confirmation_accepts_linkedin_sent_message(mocker, easy_applier):
    body = mocker.Mock()
    body.text = "Your application was sent to Example Co."
    easy_applier.driver.find_element.return_value = body
    waiter = mocker.patch("src.aihawk_easy_applier.WebDriverWait").return_value
    waiter.until.side_effect = lambda condition: condition(easy_applier.driver)

    easy_applier._wait_for_submission_confirmation()

    waiter.until.assert_called_once()


def test_wait_for_submission_confirmation_fails_closed(mocker, easy_applier):
    waiter = mocker.patch("src.aihawk_easy_applier.WebDriverWait").return_value
    waiter.until.side_effect = TimeoutException

    with pytest.raises(ApplicationSubmissionUnconfirmed, match="did not confirm"):
        easy_applier._wait_for_submission_confirmation()


def test_submit_button_requires_linkedin_confirmation(mocker, easy_applier):
    button = mocker.Mock()
    button.text = "Submit application"
    mocker.patch.object(easy_applier.driver, "find_element", return_value=button)
    mocker.patch.object(easy_applier, "_unfollow_company")
    confirmation = mocker.patch.object(easy_applier, "_wait_for_submission_confirmation")
    mocker.patch("src.aihawk_easy_applier.time.sleep")

    assert easy_applier._next_or_submit() is True

    button.click.assert_called_once()
    confirmation.assert_called_once()


def test_check_for_premium_redirect_no_redirect(mocker, easy_applier):
    """Test that check_for_premium_redirect works when there's no redirect."""
    mock_job = mock.Mock()
    easy_applier.driver.current_url = "https://www.linkedin.com/jobs/view/1234"

    easy_applier.check_for_premium_redirect(mock_job)
    easy_applier.driver.get.assert_not_called()


def test_check_for_premium_redirect_with_redirect(mocker, easy_applier):
    """Test that check_for_premium_redirect handles AIHawk Premium redirects."""
    mock_job = mock.Mock()
    easy_applier.driver.current_url = "https://www.linkedin.com/premium"
    mock_job.link = "https://www.linkedin.com/jobs/view/1234"

    with pytest.raises(Exception, match="Redirected to AIHawk Premium page and failed to return"):
        easy_applier.check_for_premium_redirect(mock_job)

    # Verify that it attempted to return to the job page 3 times
    assert easy_applier.driver.get.call_count == 3
