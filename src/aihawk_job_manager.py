import json
import os
import random
import re
import time
from itertools import product
from pathlib import Path

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

import src.utils as utils
from app_config import MINIMUM_WAIT_TIME
from src.application_tracker import ApplicationTracker, ApplicationTrackerError
from src.job import Job
from src.aihawk_easy_applier import (
    AIHawkEasyApplier,
    ApplicationSubmissionUnconfirmed,
    JobBelowMatchThreshold,
)
from loguru import logger
import urllib.parse


JOB_CARD_SELECTORS = (
    "li[data-occludable-job-id]",
    "li.jobs-search-results__list-item",
    ".jobs-search-results__list-item",
    ".job-card-container",
)


class LinkedInSessionExpired(RuntimeError):
    pass


class EnvironmentKeys:
    def __init__(self):
        logger.debug("Initializing EnvironmentKeys")
        self.skip_apply = self._read_env_key_bool("SKIP_APPLY")
        self.disable_description_filter = self._read_env_key_bool("DISABLE_DESCRIPTION_FILTER")
        logger.debug(f"EnvironmentKeys initialized: skip_apply={self.skip_apply}, disable_description_filter={self.disable_description_filter}")

    @staticmethod
    def _read_env_key(key: str) -> str:
        value = os.getenv(key, "")
        logger.debug(f"Read environment key {key}: {value}")
        return value

    @staticmethod
    def _read_env_key_bool(key: str) -> bool:
        value = os.getenv(key) == "True"
        logger.debug(f"Read environment key {key} as bool: {value}")
        return value


class AIHawkJobManager:
    def __init__(self, driver):
        logger.debug("Initializing AIHawkJobManager")
        self.driver = driver
        self.set_old_answers = set()
        self.easy_applier_component = None
        self.seen_jobs = []
        self.application_tracker = None
        self.resume_path = None
        self.max_pages_per_search = 1
        self.minimum_profile_match_score = 60
        self.min_applicants = 0
        self.max_applicants = float("inf")
        logger.debug("AIHawkJobManager initialized successfully")

    def set_parameters(self, parameters):
        logger.debug("Setting parameters for AIHawkJobManager")
        self.company_blacklist = parameters.get('company_blacklist', []) or []
        self.title_blacklist = parameters.get('title_blacklist', []) or []
        self.location_blacklist = parameters.get('location_blacklist', []) or []
        self.positions = parameters.get('positions', [])
        self.locations = parameters.get('locations', [])
        self.max_pages_per_search = parameters.get('max_pages_per_search', 1)
        self.minimum_profile_match_score = parameters.get('minimum_profile_match_score', 60)
        self.apply_once_at_company = parameters.get('apply_once_at_company', False)
        self.base_search_url = self.get_base_search_url(parameters)
        self.seen_jobs = []

        job_applicants_threshold = parameters.get('job_applicants_threshold', {})
        self.min_applicants = job_applicants_threshold.get('min_applicants', 0)
        self.max_applicants = job_applicants_threshold.get('max_applicants')

        resume_path = parameters.get('uploads', {}).get('resume', None)
        self.resume_path = Path(resume_path) if resume_path and Path(resume_path).exists() else None
        self.output_file_directory = Path(parameters['outputFileDirectory'])
        self.application_tracker = ApplicationTracker(
            self.output_file_directory / "job_applications.xlsx"
        )
        try:
            self.application_tracker.sync_existing_results(self.output_file_directory)
        except ApplicationTrackerError as exc:
            logger.error(
                "Application history remains in JSON, but Excel tracker could not be initialized: {}",
                exc,
            )
        self.env_config = EnvironmentKeys()
        logger.debug("Parameters set successfully")

    def set_gpt_answerer(self, gpt_answerer):
        logger.debug("Setting GPT answerer")
        self.gpt_answerer = gpt_answerer

    def set_resume_generator_manager(self, resume_generator_manager):
        logger.debug("Setting resume generator manager")
        self.resume_generator_manager = resume_generator_manager

    def start_collecting_data(self):
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        page_sleep = 0
        minimum_time = 60 * 5
        minimum_page_time = time.time() + minimum_time

        for position, location in searches:
            job_page_number = -1
            utils.printyellow(f"Collecting data for {position} in {location}.")
            try:
                while True:
                    page_sleep += 1
                    job_page_number += 1
                    utils.printyellow(f"Going to job page {job_page_number}")
                    self.next_job_page(position, location, job_page_number)
                    time.sleep(random.uniform(1.5, 3.5))
                    utils.printyellow("Starting the collecting process for this page")
                    self.read_jobs()
                    utils.printyellow("Collecting data on this page has been completed!")

                    time_left = minimum_page_time - time.time()
                    if time_left > 0:
                        utils.printyellow(f"Sleeping for {time_left} seconds.")
                        time.sleep(time_left)
                        minimum_page_time = time.time() + minimum_time
                    if page_sleep % 5 == 0:
                        sleep_time = random.randint(1, 5)
                        utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                        time.sleep(sleep_time)
                        page_sleep += 1
            except LinkedInSessionExpired:
                raise
            except Exception:
                pass
            time_left = minimum_page_time - time.time()
            if time_left > 0:
                utils.printyellow(f"Sleeping for {time_left} seconds.")
                time.sleep(time_left)
                minimum_page_time = time.time() + minimum_time
            if page_sleep % 5 == 0:
                sleep_time = random.randint(50, 90)
                utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                time.sleep(sleep_time)
                page_sleep += 1

    def start_applying(self):
        logger.debug("Starting job application process")
        self.easy_applier_component = AIHawkEasyApplier(self.driver, self.resume_path, self.set_old_answers,
                                                          self.gpt_answerer, self.resume_generator_manager)
        self.easy_applier_component.minimum_profile_match_score = (
            self.minimum_profile_match_score
        )
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        if not searches:
            logger.warning("No position/location searches are configured; nothing to apply for.")
            return

        for search_index, (position, location) in enumerate(searches):
            job_page_number = -1
            logger.debug(f"Starting the search for {position} in {location}.")

            try:
                while job_page_number + 1 < self.max_pages_per_search:
                    job_page_number += 1
                    logger.debug(f"Going to job page {job_page_number}")
                    self.next_job_page(position, location, job_page_number)
                    time.sleep(random.uniform(1.5, 3.5))
                    logger.debug("Starting the application process for this page...")

                    try:
                        jobs = self.get_jobs_from_page()
                        if not jobs:
                            logger.debug("No more jobs found on this page. Exiting loop.")
                            break
                    except Exception as e:
                        logger.error(f"Failed to retrieve jobs: {e}")
                        break

                    try:
                        self.apply_jobs()
                    except Exception as e:
                        logger.error(f"Error during job application: {e}")
                        continue

                    logger.debug("Applying to jobs on this page has been completed!")

                    if job_page_number + 1 < self.max_pages_per_search:
                        logger.info(
                            "Waiting %s seconds before the next results page.",
                            MINIMUM_WAIT_TIME,
                        )
                        time.sleep(MINIMUM_WAIT_TIME)
            except LinkedInSessionExpired:
                raise
            except Exception as e:
                logger.error(f"Unexpected error during job search: {e}")
                continue

            if search_index + 1 < len(searches):
                logger.info(
                    "Waiting %s seconds before the next search.",
                    MINIMUM_WAIT_TIME,
                )
                time.sleep(MINIMUM_WAIT_TIME)

    def get_jobs_from_page(self):
        if self._has_no_job_results():
            logger.info("LinkedIn reports no matching jobs for this search.")
            return []

        job_list_elements = self._find_job_card_elements()
        if job_list_elements:
            logger.info("Found %s job cards.", len(job_list_elements))
            try:
                job_results = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
            except NoSuchElementException:
                job_results = None
            if job_results is not None:
                utils.scroll_slow(self.driver, job_results)
                utils.scroll_slow(self.driver, job_results, step=300, reverse=True)
                job_list_elements = self._find_job_card_elements() or job_list_elements
            return job_list_elements

        logger.warning(
            "No job cards matched supported selectors. Current page: %s (%s).",
            self.driver.title,
            self.driver.current_url,
        )
        return []

    def _has_no_job_results(self) -> bool:
        try:
            no_jobs_element = self.driver.find_element(
                By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand'
            )
            if 'No matching jobs found' in no_jobs_element.text:
                return True
        except NoSuchElementException:
            pass
        page_source = str(self.driver.page_source).lower()
        return (
            "unfortunately, things aren't looking" in page_source
            or "no matching jobs found" in page_source
        )

    def _find_job_card_elements(self):
        for selector in JOB_CARD_SELECTORS:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return elements
        return []

    def read_jobs(self):
        if self._has_no_job_results():
            raise RuntimeError("No matching jobs on this page.")
        job_list_elements = self._find_job_card_elements()
        if not job_list_elements:
            raise RuntimeError(
                f"No job cards matched supported selectors. Current page: "
                f"{self.driver.title} ({self.driver.current_url})."
            )
        job_list = [Job(*self.extract_job_information_from_tile(job_element)) for job_element in job_list_elements] 
        for job in job_list:            
            if self.is_blacklisted(job.title, job.company, job.link, job.location):
                utils.printyellow(f"Blacklisted {job.title} at {job.company} in {job.location}, skipping...")
                self.write_to_file(job, "skipped")
                continue
            try:
                self.write_to_file(job,'data')
            except Exception as e:
                self.write_to_file(job, "failed")
                continue

    def apply_jobs(self):
        if self._has_no_job_results():
            logger.info("LinkedIn reports no matching jobs for this search.")
            return
        job_list_elements = self._find_job_card_elements()

        if not job_list_elements:
            logger.debug("No job class elements found on page, skipping")
            return

        job_list = [
            (Job(*self.extract_job_information_from_tile(job_element)), job_element)
            for job_element in job_list_elements
        ]

        for job, job_element in job_list:

            logger.debug(f"Starting applicant for job: {job.title} at {job.company}")

            if self.is_previously_failed_to_apply(job.link):
                logger.debug(f"Previously failed to apply for {job.title} at {job.company}, skipping...")
                continue
            if self.is_blacklisted(job.title, job.company, job.link, job.location):
                logger.debug(f"Job blacklisted: {job.title} at {job.company} in {job.location}")
                self.write_to_file(job, "skipped")
                continue
            if self.is_already_applied_to_job(job.title, job.company, job.link):
                self.write_to_file(job, "skipped")
                continue
            if self.is_already_applied_to_company(job.company):
                self.write_to_file(job, "skipped")
                continue
            if job.apply_method.lower() != "easy apply":
                logger.info(
                    f"Skipping {job.title} at {job.company} because LinkedIn "
                    "does not mark it as Easy Apply."
                )
                self.seen_jobs.append(job.link)
                continue
            applicant_count = self._get_applicant_count(job_element.text)
            if applicant_count is not None and (
                applicant_count < self.min_applicants
                or (
                    self.max_applicants is not None
                    and applicant_count > self.max_applicants
                )
            ):
                logger.info(
                    "Skipping %s at %s because applicant count %s is outside %s-%s.",
                    job.title,
                    job.company,
                    applicant_count,
                    self.min_applicants,
                    self.max_applicants,
                )
                self.write_to_file(job, "skipped_due_to_applicants")
                continue
            try:
                self.easy_applier_component.job_apply(job)
                self.write_to_file(job, "success")
                self.seen_jobs.append(job.link)
                logger.debug(f"Applied to job: {job.title} at {job.company}")
            except JobBelowMatchThreshold as e:
                logger.info(
                    "Skipping %s at %s: profile match %s%% is below the %s%% minimum.",
                    job.title,
                    job.company,
                    job.profile_match_score,
                    self.minimum_profile_match_score,
                )
                self.write_to_file(job, "skipped_low_match")
                self.seen_jobs.append(job.link)
            except ApplicationSubmissionUnconfirmed as e:
                logger.error(
                    "Submission state is unconfirmed for %s at %s: %s",
                    job.title,
                    job.company,
                    e,
                )
                self.write_to_file(job, "unconfirmed")
                self.seen_jobs.append(job.link)
            except Exception as e:
                logger.error(f"Failed to apply for {job.title} at {job.company}: {e}")
                self.write_to_file(job, "failed")
                continue

    @staticmethod
    def _get_applicant_count(job_card_text):
        if not isinstance(job_card_text, str):
            return None
        match = re.search(r"\b(over\s+)?([\d,]+)\s+applicants?\b", job_card_text, re.IGNORECASE)
        if not match:
            return None
        count = int(match.group(2).replace(",", ""))
        return count + 1 if match.group(1) else count

    def write_to_file(self, job, file_name):
        logger.debug(f"Writing job application result to file: {file_name}")
        selected_resume = job.pdf_path or (str(self.resume_path) if self.resume_path else "")
        pdf_path = Path(selected_resume).resolve().as_uri() if selected_resume else ""
        data = {
            "company": job.company,
            "job_title": job.title,
            "link": job.link,
            "job_recruiter": job.recruiter_link,
            "job_location": job.location,
            "pdf_path": pdf_path,
            "profile_match_score": getattr(job, "profile_match_score", None),
        }
        file_path = self.output_file_directory / f"{file_name}.json"
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([data], f, indent=4)
                logger.debug(f"Job data written to new file: {file_name}")
        else:
            with open(file_path, 'r+', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    logger.error(f"JSON decode error in file: {file_path}")
                    existing_data = []
                existing_data.append(data)
                f.seek(0)
                json.dump(existing_data, f, indent=4)
                f.truncate()
                logger.debug(f"Job data appended to existing file: {file_name}")
        if self.application_tracker is not None:
            try:
                self.application_tracker.record(data, file_name)
            except ApplicationTrackerError as exc:
                logger.error(
                    "Job status was saved to JSON, but Excel tracker update failed. "
                    "Close the workbook if it is open in Excel, then restart to sync: {}",
                    exc,
                )

    def get_base_search_url(self, parameters):
        logger.debug("Constructing base search URL")
        url_parts = []
        if parameters['remote']:
            url_parts.append("f_CF=f_WRA")
        experience_level_ids = {
            'internship': '1',
            'entry': '2',
            'associate': '3',
            'mid-senior level': '4',
            'director': '5',
            'executive': '6',
        }
        experience_levels = [
            level_id
            for level, level_id in experience_level_ids.items()
            if parameters.get('experienceLevel', {}).get(level, False)
        ]
        if experience_levels:
            url_parts.append(f"f_E={','.join(experience_levels)}")
        url_parts.append(f"distance={parameters['distance']}")
        job_types = [key[0].upper() for key, value in parameters.get('jobTypes', {}).items() if value]
        if job_types:
            url_parts.append(f"f_JT={','.join(job_types)}")
        date_mapping = {
            "all time": "",
            "month": "&f_TPR=r2592000",
            "week": "&f_TPR=r604800",
            "24 hours": "&f_TPR=r86400"
        }
        date_param = next((v for k, v in date_mapping.items() if parameters.get('date', {}).get(k)), "")
        url_parts.append("f_AL=true")
        base_url = "&".join(url_parts)
        full_url = f"?{base_url}{date_param}"
        logger.debug(f"Base search URL constructed: {full_url}")
        return full_url

    def next_job_page(self, position, location, job_page):
        logger.debug(f"Navigating to next job page: {position} in {location}, page {job_page}")
        query = urllib.parse.parse_qsl(self.base_search_url.lstrip("?"))
        query.extend([
            ("keywords", position),
            ("location", location),
            ("start", str(job_page * 25)),
        ])
        search_url = f"https://www.linkedin.com/jobs/search/?{urllib.parse.urlencode(query)}"
        self.driver.get(search_url)
        current_url = self.driver.current_url
        if "linkedin.com/login" in current_url or "linkedin.com/checkpoint/" in current_url:
            raise LinkedInSessionExpired(
                "LinkedIn redirected the job search to sign-in or a security checkpoint."
            )
        logger.debug(f"Opened LinkedIn job search URL: {search_url}")

    def extract_job_information_from_tile(self, job_tile):
        logger.debug("Extracting job information from tile")
        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        try:
            title_links = job_tile.find_elements(
                By.CSS_SELECTOR,
                'a.job-card-list__title, a[href*="/jobs/view/"]',
            )
            if title_links:
                title_link = title_links[0]
                title_text = title_link.find_elements(By.TAG_NAME, 'strong')
                job_title = title_text[0].text if title_text else title_link.text
                href = title_link.get_attribute('href') or ""
                link = href.split('?')[0]
            else:
                job_title = job_tile.find_element(
                    By.CLASS_NAME, 'job-card-list__title'
                ).text
                link = job_tile.find_element(
                    By.CLASS_NAME, 'job-card-list__title'
                ).get_attribute('href').split('?')[0]

            company_elements = job_tile.find_elements(
                By.CSS_SELECTOR,
                '.job-card-container__primary-description, .artdeco-entity-lockup__subtitle',
            )
            if company_elements:
                company = company_elements[0].text
            logger.debug(f"Job information extracted: {job_title} at {company}")
        except NoSuchElementException:
            logger.warning("Some job information (title, link, or company) is missing.")
        try:
            location_elements = job_tile.find_elements(
                By.CSS_SELECTOR,
                '.job-card-container__metadata-item, .artdeco-entity-lockup__caption',
            )
            if location_elements:
                job_location = location_elements[0].text
        except NoSuchElementException:
            logger.warning("Job location is missing.")
        apply_method_elements = job_tile.find_elements(
            By.CSS_SELECTOR,
            '.job-card-container__apply-method, .job-card-container__footer-item',
        )
        apply_method_text = " ".join(element.text for element in apply_method_elements)
        if not apply_method_text:
            apply_method_text = job_tile.text
        apply_method = (
            "Easy Apply"
            if "easy apply" in apply_method_text.lower()
            or "f_AL=true" in self.base_search_url
            else "Not Easy Apply"
        )

        return job_title, company, job_location, link, apply_method

    def is_blacklisted(self, job_title, company, link, job_location):
        logger.debug(f"Checking if job is blacklisted: {job_title} at {company} in {job_location}")
        job_title_words = job_title.lower().split(' ')
        title_blacklisted = any(word in job_title_words for word in map(str.lower, self.title_blacklist))
        company_blacklisted = company.strip().lower() in (word.strip().lower() for word in self.company_blacklist)
        location_blacklisted= job_location.strip().lower() in (word.strip().lower() for word in self.location_blacklist)
        link_seen = link in self.seen_jobs
        is_blacklisted = title_blacklisted or company_blacklisted or location_blacklisted or link_seen
        logger.debug(f"Job blacklisted status: {is_blacklisted}")

        return title_blacklisted or company_blacklisted or location_blacklisted or link_seen

    def is_already_applied_to_job(self, job_title, company, link):
        link_seen = link in self.seen_jobs
        if link_seen:
            logger.debug(f"Already applied to job: {job_title} at {company}, skipping...")
        return link_seen

    def is_already_applied_to_company(self, company):
        if not self.apply_once_at_company:
            return False

        output_files = ["success.json", "unconfirmed.json"]
        for file_name in output_files:
            file_path = self.output_file_directory / file_name
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                        for applied_job in existing_data:
                            if applied_job['company'].strip().lower() == company.strip().lower():
                                logger.debug(
                                    f"Already applied at {company} (once per company policy), skipping...")
                                return True
                    except json.JSONDecodeError:
                        continue
        return False

    def is_previously_failed_to_apply(self, link):
        for file_name in ("failed", "unconfirmed"):
            file_path = self.output_file_directory / f"{file_name}.json"
            if not file_path.exists():
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    logger.error(f"JSON decode error in file: {file_path}")
                    continue
            if any(data.get("link") == link for data in existing_data):
                return True
                
        return False
