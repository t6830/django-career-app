import litellm
import os
import logging
import json
from decouple import config
import json_repair

logger = logging.getLogger(__name__)

def get_resume_analysis_with_llm(resume_text, job_description, job_requirements_list):
    """
    Parses resume text, scores it against a job description, and extracts key information
    using a single LLM call.  Can also return the resume in markdown format.

    Args:
        resume_text (str): The plain text of the resume.
        job_description (str): The job description text.
        job_requirements_list (list): List of dicts, e.g., 
                                      [{'name': 'Python', 'weight': 0.8}, ...].

    Returns:
        dict: A dictionary containing 'parsed_data' and 'ai_score'. 
              If LLM call fails or response is malformed, it returns a dummy structure 
              with error information.
    """
    model = config('LLM_MODEL_NAME', default='gemini/gemini-pro')

    # --- Default dummy response structure for error cases ---
    # This structure is returned if the LLM call fails, JSON is malformed,
    # or essential keys are missing from the LLM response.
    dummy_response_template = {
        "parsed_data": {
            "first_name": "Dummy",
            "last_name": "Candidate",
            "contact_info": {
                "email": "candidate_from_resume@example.com",
                "phone_number": "123-555-0000",
                "linkedin_profile": "linkedin.com/in/resumecandidate"
            },
            "latest_education": {
                "latest_degree": "Master of Science",
                "school": "Tech University",
                "major": "Computer Science",
                "graduate_year": 2023
            },
            "latest_work_experience": {
                "current_title": "Senior Software Engineer",
                "company_name": "Innovate Corp" # Maps to latest_work_organization
            },
            "top_tags": ["Problem Solver", "Team Player", "Quick Learner"], # Updated dummy tags
            "error": "LLM call failed or response malformed", # Generic error for parsed_data
            "error_detail": "See top-level error_detail for more info."
        },
        "ai_score": -1.0, # Dummy score
        "resume_markdown": "Dummy resume in markdown format",
        "error": "LLM call failed or response malformed", # Top-level error
        "error_detail": "Initial error placeholder"
    }

    requirements_str = ", ".join([f"{req['name']} (weight: {req.get('weight', 1.0)})" for req in job_requirements_list])

    prompt = (
        f"Parse the resume, score it against the job description and requirements, and return a single JSON object. "
        f"The JSON object must have three top-level keys: 'parsed_data', 'ai_score', and 'resume_markdown'.\n"
        f"'parsed_data' should be a JSON object containing: "
        f"'first_name' (string), "
        f"'last_name' (string), "
        f"'contact_info' (dictionary with 'email', 'phone_number', 'linkedin_profile'), "
        f"'latest_education' (dictionary with 'latest_degree', 'school', 'major', 'graduate_year'), "
        f"'latest_work_experience' (dictionary with 'current_title', 'company_name'), and "
        f"'top_tags' (list of 3 words). For the 'top_tags' field within 'parsed_data', "
        f"provide a list of 3 words. These strings should represent the top 3 achievements or "
        f"unique selling points of the applicant that are most likely to differentiate them from "
        f"other candidates for this specific job, in particular the requirements listed below.\n"
        f"'ai_score' should be a numerical score between 0 and 100.\n"
        f"'resume_markdown' should be the resume in markdown format.\n\n"
        f"Resume text: \"\"\"{resume_text}\"\"\"\n\n"
        f"Job Description: \"\"\"{job_description}\"\"\"\n\n"
        f"Requirements: \"\"\"{requirements_str}\"\"\"\n\n"
        f"Return ONLY the JSON object with the three top-level keys."
    )

    messages = [{"role": "user", "content": prompt}]

    final_result = dummy_response_template.copy()  # Initialize with dummy response
    final_result["parsed_data"] = dummy_response_template["parsed_data"].copy()  # Ensure deep copy for nested dict

    try:
        logger.info(f"Attempting LLM call for combined parsing and scoring. Model: {model}")
        response = litellm.completion(
            model=model,
            messages=messages,
            api_key=config('GEMINI_API_KEY', default='your_gemini_api_key_here_if_not_set'),
        )

        if response and response.choices and response.choices[0].message and response.choices[0].message.content:
            content = response.choices[0].message.content
            logger.info("LLM call successful, attempting to parse response.")

            try:
                # Attempt to repair and parse the JSON response
                repaired_content = json_repair.repair_json(content, return_objects=False)
                llm_output = json.loads(repaired_content)

                # Validate structure and extract data
                if isinstance(llm_output, dict) and \
                        "parsed_data" in llm_output and isinstance(llm_output["parsed_data"], dict) and \
                        "ai_score" in llm_output and isinstance(llm_output["ai_score"], (int, float)) and \
                        "resume_markdown" in llm_output and isinstance(llm_output["resume_markdown"], str):

                    final_result["parsed_data"] = llm_output["parsed_data"]
                    final_result["ai_score"] = float(llm_output["ai_score"])
                    final_result["resume_markdown"] = llm_output["resume_markdown"]

                    # Ensure all expected nested keys in parsed_data are present, fill with defaults if not
                    # This maintains a consistent structure for parsed_data.
                    default_parsed_keys = dummy_response_template["parsed_data"]
                    for key, default_value in default_parsed_keys.items():
                        if key not in final_result["parsed_data"]:
                            final_result["parsed_data"][key] = default_value
                            logger.warning(f"LLM response missing '{key}' in 'parsed_data'. Using default.")
                        # Ensure nested dictionaries are also dictionaries
                        elif isinstance(default_value, dict) and not isinstance(final_result["parsed_data"][key], dict):
                            logger.warning(f"LLM response for '{key}' should be a dict, but it's not. Using default sub-structure.")
                            final_result["parsed_data"][key] = default_value

                    # Clear top-level errors if successful
                    final_result.pop("error", None)
                    final_result.pop("error_detail", None)
                    # Clear parsed_data errors if main parsing was successful
                    final_result["parsed_data"].pop("error", None)
                    final_result["parsed_data"].pop("error_detail", None)
                    logger.info("Successfully parsed LLM response and extracted data.")

                else:
                    logger.error(
                        f"LLM response JSON structure is invalid. Missing 'parsed_data', 'ai_score', or 'resume_markdown', or types are incorrect. Content: {content}")
                    final_result["error_detail"] = "LLM response JSON structure invalid. Missing 'parsed_data', 'ai_score', or 'resume_markdown', or types are incorrect."

            except json.JSONDecodeError as json_err:
                logger.error(
                    f"LLM response was not valid JSON despite repair attempt: {json_err}. Content: {content}",
                    exc_info=True)
                final_result["error_detail"] = f"LLM response was not valid JSON: {str(json_err)}"
            except Exception as e:  # Catch other errors during parsing/validation
                logger.error(f"Error processing LLM response content: {e}. Content: {content}", exc_info=True)
                final_result["error_detail"] = f"Error processing LLM response content: {str(e)}"

        else:
            logger.warning("LLM call 'succeeded' but response format was unexpected (e.g., no content).")
            final_result["error_detail"] = "LLM response format unexpected (e.g., no content)."

    except litellm.RateLimitError as rle:
        logger.error(f"LLM call failed due to rate limiting: {rle}", exc_info=True)
        final_result["error"] = "LLM call failed (Rate Limit)"
        final_result["error_detail"] = str(rle)
    except litellm.APIConnectionError as ace:
        logger.error(f"LLM call failed due to API connection error: {ace}", exc_info=True)
        final_result["error"] = "LLM call failed (API Connection)"
        final_result["error_detail"] = str(ace)
    except litellm.APIError as apie:  # Catch other litellm API errors
        logger.error(f"LLM call failed due to API error: {apie}", exc_info=True)
        final_result["error"] = "LLM call failed (API Error)"
        final_result["error_detail"] = str(apie)
    except Exception as e:
        logger.error(f"General failure during LLM call or processing: {e}", exc_info=True)
        final_result["error"] = "LLM call failed (General Exception)"
        final_result["error_detail"] = str(e)

    return final_result
