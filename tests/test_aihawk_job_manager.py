from src.job import Job
from unittest import mock
from pathlib import Path
import os
import pytest
from urllib.parse import parse_qs, urlparse
from src.aihawk_job_manager import AIHawkJobManager, LinkedInSessionExpired
from src.aihawk_easy_applier import (
    ApplicationSubmissionUnconfirmed,
    JobBelowMatchThreshold,
)
from selenium.common.exceptions import NoSuchElementException
from loguru import logger


@pytest.fixture
def job_manager(mocker):
    """Fixture to create a AIHawkJobManager instance with mocked driver."""
    mock_driver = mocker.Mock()
    return AIHawkJobManager(mock_driver)


def test_initialization(job_manager):
    """Test AIHawkJobManager initialization."""
    assert job_manager.driver is not None
    assert job_manager.set_old_answers == set()
    assert job_manager.easy_applier_component is None


def test_set_parameters(mocker, job_manager):
    """Test setting parameters for the AIHawkJobManager."""
    # Mocking os.path.exists to return True for the resume path
    mocker.patch('pathlib.Path.exists', return_value=True)

    params = {
        'company_blacklist': ['Company A', 'Company B'],
        'title_blacklist': ['Intern', 'Junior'],
        'positions': ['Software Engineer', 'Data Scientist'],
        'locations': ['New York', 'San Francisco'],
        'apply_once_at_company': True,
        'uploads': {'resume': '/path/to/resume'},  # Resume path provided here
        'outputFileDirectory': '/path/to/output',
        'job_applicants_threshold': {
            'min_applicants': 5,
            'max_applicants': 50
        },
        'remote': False,
        'distance': 50,
        'date': {'all time': True}
    }

    job_manager.set_parameters(params)

    # Normalize paths to handle platform differences (e.g., Windows vs Unix-like systems)
    assert str(job_manager.resume_path) == os.path.normpath('/path/to/resume')
    assert str(job_manager.output_file_directory) == os.path.normpath(
        '/path/to/output')


def test_search_url_encodes_keywords_location_and_experience_levels(job_manager):
    parameters = {
        'remote': False,
        'distance': 100,
        'experienceLevel': {
            'internship': False,
            'entry': True,
            'associate': True,
            'mid-senior level': True,
            'director': False,
            'executive': False,
        },
        'jobTypes': {'full-time': True},
        'date': {'all time': True},
    }
    job_manager.base_search_url = job_manager.get_base_search_url(parameters)
    job_manager.driver.current_url = 'https://www.linkedin.com/jobs/search/'

    job_manager.next_job_page('C++ Engineer', 'New York, NY', 2)

    search_url = job_manager.driver.get.call_args.args[0]
    query = parse_qs(urlparse(search_url).query)
    assert query['keywords'] == ['C++ Engineer']
    assert query['location'] == ['New York, NY']
    assert query['start'] == ['50']
    assert query['f_E'] == ['2,3,4']
    assert query['f_AL'] == ['true']
    assert 'f_CF' not in query
    assert 'f_TPR' not in query


def test_job_card_selectors_fall_back_to_current_card_markup(mocker, job_manager):
    card = mocker.Mock()
    mocker.patch.object(job_manager.driver, 'find_elements', side_effect=[[], [card]])

    assert job_manager._find_job_card_elements() == [card]


def test_search_filter_marks_results_as_easy_apply(mocker, job_manager):
    title_link = mocker.Mock()
    title_link.text = "Frontend Developer"
    title_link.get_attribute.return_value = "https://www.linkedin.com/jobs/view/123"
    title_link.find_elements.return_value = []
    company = mocker.Mock()
    company.text = "Example Co."
    location = mocker.Mock()
    location.text = "Remote"
    job_card = mocker.Mock()
    job_card.text = "Frontend Developer Example Co. Remote"
    job_card.find_elements.side_effect = [
        [title_link],
        [company],
        [location],
        [],
    ]
    job_manager.base_search_url = "?f_AL=true"

    extracted = job_manager.extract_job_information_from_tile(job_card)

    assert extracted[-1] == "Easy Apply"


def test_job_search_stops_if_linkedin_requires_reauthentication(job_manager):
    job_manager.base_search_url = "?distance=100"
    job_manager.driver.current_url = "https://www.linkedin.com/login"

    with pytest.raises(LinkedInSessionExpired, match="security checkpoint"):
        job_manager.next_job_page("Software engineer", "India", 0)


def next_job_page(self, position, location, job_page):
    logger.debug(f"Navigating to next job page: {position} in {location}, page {job_page}")
    self.driver.get(
        f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}&location={location}&start={job_page * 25}")


def test_get_jobs_from_page_no_jobs(mocker, job_manager):
    """Test get_jobs_from_page when no jobs are found."""
    mocker.patch.object(job_manager.driver, 'find_element',
                        side_effect=NoSuchElementException)
    mocker.patch.object(job_manager.driver, 'find_elements', return_value=[])
    mocker.patch.object(job_manager.driver, 'page_source', new="")

    jobs = job_manager.get_jobs_from_page()
    assert jobs == []


def test_get_jobs_from_page_with_jobs(mocker, job_manager):
    """Test get_jobs_from_page when job elements are found."""
    # Mock the no_jobs_element to behave correctly
    mock_no_jobs_element = mocker.Mock()
    mock_no_jobs_element.text = "No matching jobs found"

    # Mocking the find_element to return the mock no_jobs_element
    mocker.patch.object(job_manager.driver, 'find_element',
                        return_value=mock_no_jobs_element)

    # Mock the page_source
    mocker.patch.object(job_manager.driver, 'page_source',
                        return_value="some page content")

    # Ensure jobs are returned as empty list due to "No matching jobs found"
    jobs = job_manager.get_jobs_from_page()
    assert jobs == []  # No jobs expected due to "No matching jobs found"


def test_apply_jobs_with_no_jobs(mocker, job_manager):
    """Test apply_jobs when no jobs are found."""
    # Mocking find_element to return a mock element that simulates no jobs
    mock_element = mocker.Mock()
    mock_element.text = "No matching jobs found"

    # Mock the driver to simulate the page source
    mocker.patch.object(job_manager.driver, 'page_source', return_value="")

    # Mock the driver to return the mock element when find_element is called
    mocker.patch.object(job_manager.driver, 'find_element',
                        return_value=mock_element)

    # Call apply_jobs and ensure no exceptions are raised
    job_manager.apply_jobs()

    # Ensure it attempted to find the job results list
    assert job_manager.driver.find_element.call_count == 1


def test_apply_jobs_with_jobs(mocker, job_manager):
    """Test apply_jobs when jobs are present."""

    # Mock no_jobs_element to simulate the absence of "No matching jobs found" banner
    no_jobs_element = mocker.Mock()
    no_jobs_element.text = ""  # Empty text means "No matching jobs found" is not present
    mocker.patch.object(job_manager.driver, 'find_element',
                        return_value=no_jobs_element)

    # Mock the page_source to simulate what the page looks like when jobs are present
    mocker.patch.object(job_manager.driver, 'page_source',
                        return_value="some job content")

    # Mock the inner find_elements to return job list items
    job_element_mock = mocker.Mock()
    # Simulating two job items
    job_elements_list = [job_element_mock, job_element_mock]
    mocker.patch.object(job_manager.driver, 'find_elements',
                        return_value=job_elements_list)

    # Mock the extract_job_information_from_tile method to return sample job info
    mocker.patch.object(job_manager, 'extract_job_information_from_tile', return_value=(
        "Title", "Company", "Location", "https://www.linkedin.com/jobs/view/123", "Easy Apply"))

    # Mock other methods like is_blacklisted, is_already_applied_to_job, and is_already_applied_to_company
    mocker.patch.object(job_manager, 'is_blacklisted', return_value=False)
    mocker.patch.object(
        job_manager, 'is_already_applied_to_job', return_value=False)
    mocker.patch.object(
        job_manager, 'is_already_applied_to_company', return_value=False)

    # Mock the AIHawkEasyApplier component
    job_manager.easy_applier_component = mocker.Mock()

    # Mock the output_file_directory as a valid Path object
    job_manager.output_file_directory = Path("/mocked/path/to/output")

    # Mock Path.exists() to always return True (so no actual file system interaction is needed)
    mocker.patch.object(Path, 'exists', return_value=True)

    # Mock the open function to prevent actual file writing
    mock_open = mocker.mock_open()
    mocker.patch('builtins.open', mock_open)

    # Run the apply_jobs method
    job_manager.apply_jobs()

    # Assertions
    assert job_manager.driver.find_elements.call_count == 1
    # Called for each job element
    assert job_manager.extract_job_information_from_tile.call_count == 2
    # Called for each job element
    assert job_manager.easy_applier_component.job_apply.call_count == 2
    mock_open.assert_called()  # Ensure that the open function was called


def test_apply_jobs_skips_jobs_not_marked_easy_apply(mocker, job_manager):
    card = mocker.Mock()
    mocker.patch.object(job_manager, '_has_no_job_results', return_value=False)
    mocker.patch.object(job_manager, '_find_job_card_elements', return_value=[card])
    mocker.patch.object(
        job_manager,
        'extract_job_information_from_tile',
        return_value=("Title", "Company", "Location", "https://example.com/job", "Not Easy Apply"),
    )
    mocker.patch.object(job_manager, 'is_previously_failed_to_apply', return_value=False)
    mocker.patch.object(job_manager, 'is_blacklisted', return_value=False)
    mocker.patch.object(job_manager, 'is_already_applied_to_job', return_value=False)
    mocker.patch.object(job_manager, 'is_already_applied_to_company', return_value=False)
    job_manager.easy_applier_component = mocker.Mock()

    job_manager.apply_jobs()

    job_manager.easy_applier_component.job_apply.assert_not_called()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("75 applicants", 75),
        ("Over 1,200 applicants", 1201),
        ("Actively reviewing applicants", None),
    ],
)
def test_get_applicant_count(text, expected):
    assert AIHawkJobManager._get_applicant_count(text) == expected


def test_apply_jobs_skips_above_configured_applicant_limit(mocker, job_manager):
    card = mocker.Mock()
    card.text = "Frontend Developer\nExample Co.\n75 applicants"
    job_manager.min_applicants = 0
    job_manager.max_applicants = 30
    mocker.patch.object(job_manager, "_has_no_job_results", return_value=False)
    mocker.patch.object(job_manager, "_find_job_card_elements", return_value=[card])
    mocker.patch.object(
        job_manager,
        "extract_job_information_from_tile",
        return_value=("Frontend Developer", "Example Co.", "Remote", "https://example.com/job", "Easy Apply"),
    )
    mocker.patch.object(job_manager, "is_previously_failed_to_apply", return_value=False)
    mocker.patch.object(job_manager, "is_blacklisted", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_job", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_company", return_value=False)
    mocker.patch.object(job_manager, "write_to_file")
    job_manager.easy_applier_component = mocker.Mock()

    job_manager.apply_jobs()

    job_manager.write_to_file.assert_called_once()
    assert job_manager.write_to_file.call_args.args[1] == "skipped_due_to_applicants"
    job_manager.easy_applier_component.job_apply.assert_not_called()


def test_apply_jobs_does_not_apply_applicant_count_limit_when_unlimited(mocker, job_manager):
    card = mocker.Mock()
    card.text = "Frontend Developer\nExample Co.\n2,000 applicants"
    job_manager.min_applicants = 0
    job_manager.max_applicants = None
    mocker.patch.object(job_manager, "_has_no_job_results", return_value=False)
    mocker.patch.object(job_manager, "_find_job_card_elements", return_value=[card])
    mocker.patch.object(
        job_manager,
        "extract_job_information_from_tile",
        return_value=("Frontend Developer", "Example Co.", "Remote", "https://example.com/job", "Easy Apply"),
    )
    mocker.patch.object(job_manager, "is_previously_failed_to_apply", return_value=False)
    mocker.patch.object(job_manager, "is_blacklisted", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_job", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_company", return_value=False)
    mocker.patch.object(job_manager, "write_to_file")
    job_manager.easy_applier_component = mocker.Mock()

    job_manager.apply_jobs()

    job_manager.easy_applier_component.job_apply.assert_called_once()


def test_apply_jobs_applies_easy_apply_once(mocker, job_manager):
    card = mocker.Mock()
    job = ("Title", "Company", "Location", "https://www.linkedin.com/jobs/view/123", "Easy Apply")
    mocker.patch.object(job_manager, '_has_no_job_results', return_value=False)
    mocker.patch.object(job_manager, '_find_job_card_elements', return_value=[card])
    mocker.patch.object(job_manager, 'extract_job_information_from_tile', return_value=job)
    mocker.patch.object(job_manager, 'is_previously_failed_to_apply', return_value=False)
    mocker.patch.object(job_manager, 'is_blacklisted', return_value=False)
    mocker.patch.object(job_manager, 'is_already_applied_to_job', return_value=False)
    mocker.patch.object(job_manager, 'is_already_applied_to_company', return_value=False)
    mocker.patch.object(job_manager, 'write_to_file')
    job_manager.easy_applier_component = mocker.Mock()

    job_manager.apply_jobs()

    job_manager.easy_applier_component.job_apply.assert_called_once()
    assert job_manager.seen_jobs == [job[3]]


def test_apply_jobs_tracks_unconfirmed_submission_without_retry(mocker, job_manager):
    card = mocker.Mock()
    job = ("Title", "Company", "Location", "https://www.linkedin.com/jobs/view/123", "Easy Apply")
    mocker.patch.object(job_manager, "_has_no_job_results", return_value=False)
    mocker.patch.object(job_manager, "_find_job_card_elements", return_value=[card])
    mocker.patch.object(job_manager, "extract_job_information_from_tile", return_value=job)
    mocker.patch.object(job_manager, "is_previously_failed_to_apply", return_value=False)
    mocker.patch.object(job_manager, "is_blacklisted", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_job", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_company", return_value=False)
    mocker.patch.object(job_manager, "write_to_file")
    job_manager.easy_applier_component = mocker.Mock()
    job_manager.easy_applier_component.job_apply.side_effect = ApplicationSubmissionUnconfirmed()

    job_manager.apply_jobs()

    assert job_manager.write_to_file.call_args.args[1] == "unconfirmed"
    assert job_manager.seen_jobs == [job[3]]


def test_apply_jobs_tracks_below_threshold_match_as_skipped(mocker, job_manager):
    card = mocker.Mock()
    job = ("Title", "Company", "Location", "https://www.linkedin.com/jobs/view/123", "Easy Apply")
    mocker.patch.object(job_manager, "_has_no_job_results", return_value=False)
    mocker.patch.object(job_manager, "_find_job_card_elements", return_value=[card])
    mocker.patch.object(job_manager, "extract_job_information_from_tile", return_value=job)
    mocker.patch.object(job_manager, "is_previously_failed_to_apply", return_value=False)
    mocker.patch.object(job_manager, "is_blacklisted", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_job", return_value=False)
    mocker.patch.object(job_manager, "is_already_applied_to_company", return_value=False)
    mocker.patch.object(job_manager, "write_to_file")
    job_manager.easy_applier_component = mocker.Mock()
    job_manager.easy_applier_component.job_apply.side_effect = JobBelowMatchThreshold()

    job_manager.apply_jobs()

    assert job_manager.write_to_file.call_args.args[1] == "skipped_low_match"
    assert job_manager.seen_jobs == [job[3]]


def test_start_applying_limits_pages_per_search(mocker, job_manager):
    job_manager.positions = ["Frontend engineer"]
    job_manager.locations = ["India", "Japan"]
    job_manager.max_pages_per_search = 1
    job_manager.resume_path = None
    job_manager.set_old_answers = set()
    job_manager.gpt_answerer = mocker.Mock()
    job_manager.resume_generator_manager = mocker.Mock()
    mocker.patch("src.aihawk_job_manager.AIHawkEasyApplier")
    mocker.patch("src.aihawk_job_manager.time.sleep")
    mocker.patch.object(job_manager, "next_job_page")
    mocker.patch.object(job_manager, "get_jobs_from_page", return_value=[mocker.Mock()])
    mocker.patch.object(job_manager, "apply_jobs")

    job_manager.start_applying()

    assert job_manager.next_job_page.call_count == 2
    assert all(call.args[2] == 0 for call in job_manager.next_job_page.call_args_list)
    assert job_manager.get_jobs_from_page.call_count == 2
    assert job_manager.apply_jobs.call_count == 2
