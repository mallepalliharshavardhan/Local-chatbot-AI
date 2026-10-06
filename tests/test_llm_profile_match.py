import pytest

from src.llm.llm_manager import GPTAnswerer


@pytest.mark.parametrize("output, expected", [("60", 60), ("Match score: 72%", 72), ("100", 100)])
def test_parse_profile_match_score(output, expected):
    assert GPTAnswerer.parse_profile_match_score(output) == expected


@pytest.mark.parametrize("output", ["", "101", "-1", "about 75", "N/A"])
def test_parse_profile_match_score_rejects_ambiguous_or_invalid_scores(output):
    with pytest.raises(ValueError):
        GPTAnswerer.parse_profile_match_score(output)


def test_score_job_match_uses_resume_profile_and_job_description(mocker):
    answerer = object.__new__(GPTAnswerer)
    answerer.llm_cheap = mocker.Mock()
    answerer.resume = "candidate resume"
    answerer.job_application_profile = "candidate profile"
    answerer.job = mocker.Mock(description="job description")
    chain = mocker.Mock()
    chain.invoke.return_value = "73"
    mocker.patch.object(answerer, "_create_chain", return_value=chain)

    assert answerer.score_job_match() == 73

