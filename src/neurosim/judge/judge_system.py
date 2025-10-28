"""
@file purpose: Comprehensive judge system for evaluating browser-use
agent runs with detailed structured feedback.
"""

import asyncio
import os
import base64
import io
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Union

from PIL import Image
from pydantic import BaseModel
from neurosim.judge.adapter import Adapter

from neurosim.judge.messages import (
    BaseMessage,
    ContentPartImageParam,
    ContentPartTextParam,
    ImageURL,
    SystemMessage,
    UserMessage,
)

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """
    Error categories for the judge system.
    """
    # Access & Authentication
    CAPTCHA_UNSOLVED = 'captcha_unsolved'
    LOGIN_FAILED = 'login_failed'
    SECURITY_BLOCK = 'security_block'

    # LLM
    RATE_LIMITED = 'rate_limited'
    LLM_CALL_ERROR = 'llm_call_error'

    # Planning / context
    INFINITE_LOOP = 'infinite_loop'
    WRONG_OUTPUT_FORMAT = 'wrong_output_format'
    NAVIGATION_ERROR = 'navigation_error'
    TIMEOUT = 'timeout'

    # Browser
    WAIT_TOO_SHORT = 'wait_too_short'
    BROWSER_CRASHES = 'browser_crashes'
    ELEMENT_INTERACTION_ERROR = 'element_interaction_error'
    IFRAME_ISSUES = 'iframe_issues'
    TOOL_FAILED = 'tool_failed'

    # Task
    PARTIAL_OUTPUT = 'partial_output'
    IMPOSSIBLE_TASK = 'impossible_task'
    PARTIAL_VIEW_LIMITATION = 'partial_view_limitation'

    # File System
    FILE_SYSTEM_MISUSE = 'file_system_misuse'
    EXTRACT_DATA_MISUSE = 'extract_data_misuse'
    DATA_NOT_SAVED = 'data_not_saved'
    CONTENT_NOT_FOUND = 'content_not_found'


class TaskCategory(Enum):
    """
    Task categories for the judge system.
    """
    EXTRACTION = 'extraction'
    INTERACTION = 'interaction'
    LOGIN = 'login'
    RESEARCH = 'research'
    SHOPPING = 'shopping'
    BOOKING = 'booking'
    COMPARISON = 'comparison'
    QA_TESTING = 'qa_testing'
    FORM_FILLING = 'form_filling'
    NAVIGATION = 'navigation'
    SEARCH = 'search'
    FILTERING = 'filtering'
    CONTENT_CREATION = 'content_creation'
    FILE_OPERATIONS = 'file_operations'
    MULTI_STEP_WORKFLOW = 'multi_step_workflow'


class JudgeResult(BaseModel):
    """
    Comprehensive evaluation result from the judge system.

    This class represents the structured output of evaluating a browser-use agent's
    performance on a given task. It includes scoring, error analysis, and actionable
    feedback for system improvements.

    Attributes:
        task_summary: One-sentence summary of what the task was trying to accomplish
        reasoning: Detailed analysis covering trajectory quality, tool usage, and output quality
        error_categories: List of ErrorCategory enums identifying specific failure modes
        final_score: Integer score from 0-100 representing percentage of task completion
        improvement_tips: Actionable suggestions for developers to fix identified issues
    """
    # Basic Information
    task_summary: str

    # Analysis
    reasoning: str
    error_categories: list[ErrorCategory]

    final_score: int

    # Developer Feedback
    improvement_tips: list[str]


def encode_image(image_path: str) -> str:
    """
    Encode an image file to base64 string for embedding in data URLs.

    Converts various image formats to JPEG and encodes as base64. Handles
    format conversion for images with transparency or palette modes.

    Args:
        image_path: Path to the image file to encode

    Returns:
        Base64-encoded string of the image, or empty string if encoding fails
    """
    try:
        with Image.open(image_path) as image:
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            elif image.mode == 'L':
                image = image.convert('RGB')
            buffered = io.BytesIO()
            image.save(buffered, format='JPEG')
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except (IOError, OSError, ValueError) as e:
        logger.error('Failed to encode image %s: %s', image_path, e)
        return ''


def truncate_text(text: str, max_length: int, from_beginning: bool = False) -> str:
    """
    Truncate text to fit within specified length limits.

    Adds truncation markers to indicate where content was cut. Can truncate
    from either the beginning or end of the text.

    Args:
        text: Text string to truncate
        max_length: Maximum allowed length including truncation markers
        from_beginning: If True, truncates from start; if False, from end

    Returns:
        Truncated text with appropriate markers
    """
    if len(text) <= max_length:
        return text
    if from_beginning:
        return '...[cut for eval]' + text[-max_length + 23:]
    else:
        return text[: max_length - 23] + '...[cut for eval]...'


def prepare_agent_steps(complete_history: list[dict]) -> list[str]:
    """
    Convert agent execution history into formatted text for evaluation.

    Processes the complete agent history to extract actions, results, and errors,
    formatting them into readable step descriptions. Truncates long content to
    keep the evaluation focused on recent actions.

    Args:
        complete_history: List of dictionaries containing agent step data

    Returns:
        List of formatted step descriptions, limited to ~15000 chars total
    """
    history_to_process = complete_history
    steps = []
    for i, step in enumerate(history_to_process):
        step_text = f'Step {i + 1}:\n'
        if step.get('model_output'):
            model_output = step['model_output']
            if isinstance(model_output, dict) and 'action' in model_output:
                action_json = json.dumps(model_output['action'], indent=1)
                if len(action_json) > 500:
                    step_text += f'Actions: {action_json[:500]}...[cut for eval system]\n'
                else:
                    step_text += f'Actions: {action_json}\n'
        if step.get('result'):
            for j, result in enumerate(step['result']):
                if isinstance(result, dict):
                    if result.get('extracted_content'):
                        content = str(result['extracted_content'])
                        if len(content) > 500:
                            step_text += f'Result {j + 1}: \
								{content[:500]}...[cut for eval system]\n'
                        else:
                            step_text += f'Result {j + 1}: {content}\n'
                    if result.get('error'):
                        error = str(result['error'])
                        if len(error) > 500:
                            step_text += f'Error {j + 1}: {error[:500]}...[cut for eval system]\n'
                        else:
                            step_text += f'Error {j + 1}: {error}\n'
        steps.append(step_text)
    # return last ~15000 chars of steps
    total_length = 0
    last_part: list[str] = []
    for step_text in reversed(steps):
        total_length += len(step_text)
        if total_length > 15000:
            break
        last_part.append(step_text)
    return last_part[::-1]


def are_images_identical(img_path1: str, img_path2: str) -> bool:
    """
    Compare two images for exact pixel-level equality.

    Handles format conversion to ensure fair comparison and checks both
    dimensions and pixel data for identity.

    Args:
        img_path1: Path to the first image
        img_path2: Path to the second image

    Returns:
        True if images are identical, False otherwise or on error
    """
    try:
        with Image.open(img_path1) as img1, Image.open(img_path2) as img2:
            if img1.mode != img2.mode:
                img1 = img1.convert('RGB')
                img2 = img2.convert('RGB')
            if img1.size != img2.size:
                return False
            return list(img1.getdata()) == list(img2.getdata())
    except (IOError, OSError, ValueError) as e:
        logger.warning('Failed to compare images %s and %s: %s',
                       img_path1, img_path2, e)
        return False


def filter_images(screenshot_paths: list[str], max_images: int) -> list[str]:
    """
    Filter screenshot list to remove duplicates and limit count.

    Removes consecutive identical images to reduce redundancy and limits
    the total number of images to the specified maximum, keeping the most
    recent unique screenshots.

    Args:
        screenshot_paths: List of paths to screenshot files
        max_images: Maximum number of images to return

    Returns:
        Filtered list of unique screenshot paths
    """
    if not screenshot_paths:
        return []
    if len(screenshot_paths) == 1:
        return screenshot_paths
    filtered_paths = screenshot_paths[1:]
    deduplicated_paths: list[str] = []
    for i, current_path in enumerate(filtered_paths):
        if i == 0:
            deduplicated_paths.append(current_path)
            continue
        previous_path = filtered_paths[i - 1]
        if not are_images_identical(current_path, previous_path):
            deduplicated_paths.append(current_path)
    if not deduplicated_paths:
        deduplicated_paths = [screenshot_paths[-1]]
    return deduplicated_paths[-max_images:] if len(deduplicated_paths) > max_images else deduplicated_paths


async def comprehensive_judge(
        task: str,
        complete_history: list[dict],
        final_result: str,
        last_message: str,
        screenshot_paths: list[str],
        model: Adapter,
        max_images: int = 10,
) -> JudgeResult:
    """
    Comprehensive evaluation of browser-use agent performance.

    This is the core judge function that analyzes agent execution using an LLM
    to provide detailed scoring and feedback. It processes the complete agent
    trajectory, final results, and screenshots to generate structured evaluation.

    Args:
        task: Original task description given to the agent
        complete_history: List of agent execution steps with actions and results
        final_result: Agent's final output or result
        last_message: Last message/input provided to the agent
        screenshot_paths: List of screenshot file paths from agent execution
        model: LLM adapter (OpenAI or Gemini) for performing evaluation
        max_images: Maximum number of screenshots to include in evaluation

    Returns:
        JudgeResult containing detailed evaluation with score and feedback

    Raises:
        Returns fallback result on any evaluation errors
    """
    # Prepare inputs
    task_truncated = truncate_text(task, 40000)
    final_result_truncated = truncate_text(
        final_result or 'No final result', 20000)
    last_message_truncated = truncate_text(
        last_message or 'No last message', 40000, from_beginning=True)
    # Agent trajectory omitted to keep prompt focused on final result and state

    selected_images = filter_images(screenshot_paths, max_images)
    if not selected_images and screenshot_paths:
        selected_images = [screenshot_paths[-1]]

    encoded_images: list[ContentPartImageParam] = []
    for img_path in selected_images:
        if Path(img_path).exists():
            encoded_img = encode_image(img_path)
            if encoded_img:
                encoded_images.append(ContentPartImageParam(
                    image_url=ImageURL(url=f'data:image/jpeg;base64,{encoded_img}')))

    error_categories_text = ', '.join(
        [category.value for category in ErrorCategory])

    system_prompt = f"""You are an expert judge evaluating browser-use agent performance.


Here is context about the agent you have to evaluate:


**AGENT ARCHITECTURE UNDERSTANDING:**
The browser-use agent operates in iterative loops receiving structured input:

**AGENT INPUT (what agent sees each step):**
1. AGENT HISTORY: Chronological event stream with previous actions and results
2. AGENT STATE: User request, file system state, todo.md contents, step info 
3. BROWSER STATE: Current URL, tabs, and interactive elements in indexed format (this represents the css selector of the element), and text of the current viewport
4. BROWSER VISION: Screenshot with bounding boxes around interactive elements
5. READ STATE: Temporary data from extract_structured_data or read_file actions

**CRITICAL: BROWSER STATE CONTAINS READABLE TEXT**
- The DOM is converted to text with indexed interactive elements: [index]<type>text content</type>
- Agent sees the browser_state of the current viewport at every step without needing extract_structured_data
- extract_structured_data gets the markdown of the entire page and not just the visible part, it then parses it to structured data based on a query and saves it to a markdown file and shows it into the read state
- Instead of extract_structured_data the agent can also scroll to get more information in the browser_state
- The browser_state is the ground truth, but can be improved if information is missing
- The agent can also read information directly from the input screenshot 

**AGENT OUTPUT FORMAT (always JSON):**
- thinking: Structured reasoning following specific patterns
- evaluation_previous_goal: Assessment of last action success/failure 
- memory: Progress tracking (1-3 sentences)
- next_goal: Clear statement of immediate objectives
- action: List of actions to execute sequentially
- results: Final output of the agent that will print out the final result or the error message
 ALWAYS parse the final agent output JSON and inspect the `results` field before applying any scoring rules.

**FINAL-ANSWER GROUNDEDNESS CHECK (run FIRST, before any other evaluation):**
1. **CRITICAL**: The agent's declared answer is provided in the **FINAL RESULT** section below. This contains the agent's actual output - NOT a summary. Examine this carefully for specific, detailed information that directly answers the task. If the **FINAL RESULT** contains specific, detailed information (names, numbers, lists, etc.) that directly answers the task requirements, the answer is likely grounded. 
2. Verify that the browser ended on a *plausible* source page. The final screenshot must not show an error page, 404, login wall, or captcha.
2a. Single blank screenshot exception: If there is exactly 1 screenshot and it is blank or black, but the browser_state shows a plausible final URL for the task and the FINAL RESULT contains specific, task-relevant details consistent with that site, treat the answer as grounded. Mark the run successful with a final score of 70 or higher, then continue scoring per normal criteria.
3. If Steps 1 and 2 succeed and there is no visual contradiction in the screenshot, assume the answer is *grounded* (not hallucinated). Mark the run **Grounded = True**
4. Grounded = True → score floor is 70. Continue with normal criteria to decide 70-79, 80-89, or 90-100.
5. Grounded = False → proceed with normal criteria and deduct as needed for missing output, tool errors, etc.

**EXPECTED AGENT BEHAVIORS:**
- Follows task output format requirements precisely (direct output vs file writing)
- Uses todo.md for long tasks above 20 steps
- Saves findings to results.md when the task is long multiple things need to be extracted on different pages
- Dont use file system for short tasks except required by the task
- Calls done action only when task complete or impossible to continue - not too early
- If the agent needs to repeat the same sub task multiple times & has a good trajectory, but hits the max step limit the score should be medium
- Analyse the screenshots. Some screenshots will have bounding boxes around interactive elements. Each interactive element should have exactly one color bounding box. If the bounding boxes look off mention that.

**EVALUATION FRAMEWORK:**
**PRIMARY EVALUATION CRITERIA (in order of importance, evaluate ONLY after the Groundedness Check):** 
1. **Task Satisfaction (Most Important)**: Did the agent accomplish what the user asked for? Focus on user intent and final outcome.
2. **Output Quality**: Is the final result in the correct format and complete? Does it match exactly what was requested?
3. **Tool Effectiveness**: Did the browser interactions work as expected? Were tools used appropriately? How many % of the tools failed?
4. **Agent Reasoning**: Quality of decision-making, planning, and problem-solving throughout the trajectory.
5. **Browser Handling**: Navigation stability, error recovery, and technical execution. If the browser crashes, does not load or a captcha blocks the task, the score must be very low.

**SCORING GUIDELINES (final_score represents % of task completion):**
- 90-100: Excellent - Task completed as requested, human-like execution
- 80-89: Very Good - Task completed with minor issues, but meets user fully requirements 
- 70-79: Good - Task completed with minor issues, core requirements satisfied
- 60-69: Partial - Some parts of task completed, but significant portions incomplete or incorrect
- 40-59: Poor - Major issues, only minor parts of task completed successfully
- 1-39: Failed - Task not completed, significant problems throughout execution
- 0: Complete failure - No meaningful progress toward task completion or completely blocked by a captcha or login

**Examples of task completion scoring:**
- If task asks for 10 items and agent finds 4 items correctly: 40
- If task completed to full user requirements but with some errors to improve in the trajectory: 85
- If task impossible due to captcha/login requirements: 0
- If we get blocked by Cloudflare challenge the final score must be 0
- If the trajectory is ideal and the output is perfect: 100

**FAILURE CONDITIONS (automatically score very low):**
- Task not completed when it should be completable
- Blocked by captcha or authentication when avoidable
- Output format completely wrong or missing and Grounded = False
- Infinite loops or severe technical failures
- Critical user requirements ignored
- Page not loaded
- Browser crashed
- Agent could not interact with required UI elements
- Do not mark Page not loaded or Browser crashed solely because the single screenshot is blank if step 2a applies and browser_state/FINAL RESULT are consistent.


**ERROR CATEGORIES TO IDENTIFY:**
{error_categories_text}


- Notes for the error categories:
- Use the main error - e.g. if we cant login and thats why we dont have an output we should use the login_failed error category
- The error category list is sequential - so check if an error before is matching better and use that instead
- captcha_unsolved includes traditional captchas, Cloudflare challenges, and any other anti-bot protection systems that block task completion
- login_failed means the agent could not login or the login was not successful.
- security_block means the agent was blocked by a security system other than captcha.
- rate_limited means the LLM call was not successful because the rate limit was reached.
- llm_call_error means the agent could not call the llm or the llm call was not successful.
- partial_output means we collected some part of the output but some is missing.
- tool_failed means a tool like scrolling or file interaction failed or can be improved because functionality which would be helpful was missing - mention that in the improvement tips
- infinite_loop means the agent is stuck in a loop and not making progress
- navigation_error means the agent could not navigate to the page or the navigation was not successful.
- timeout means the agent timed out and while completing the task/
- wrong_output_format means the output is not in the requested format
- element_interaction_error means that our extraction of the DOM is not correct. E.g. we missed to detect a crucial button and the agent does not see it with a [index]. This can be verified if you look how we highlight elements in the screenshot.
- iframe_issues means we dont parse elements in the iframe correctly. E.g. we missed to detect a crucial button and the agent does not see it with a [index].
- impossible_task means the task is impossible to complete because the site is down, the dates are in the past or information is missing
- file_system_misuse means using read_file/write_file for short tasks when direct output would be appropriate. NOTE: extract_structured_data automatically saves to files as part of its core functionality - this is NOT file system misuse and expected behavior.
- partial_view_limitation means the agent is not able to see the whole page and is missing information. E.g. the agent is not able to see the whole page because it is not scrolling or the page is too big.
- data_not_saved means the agent did not save the data to the file system or the data was not found.
- content_not_found means the agent did not find the content on the page.


**Improvement Tips (Actionable Developer Guidance):**
Format: "Error Category: Specific improvement suggestion"
Examples:
- "Login error on sheets.google.com: Build a dedicated Google Sheets login function"
- "Element not found: Improve the DOM extraction layer to correctly include buttons in the navigation bar of the website check24.de"
- "Load timeout: Implement better wait strategies for dynamic content to wait until the page is fully loaded"
- "File system misuse: The agent used the read and write file tools for short tasks even it could have outputted the information directly. Adapt the system prompt to not use the file system for short tasks."


**IMPORTANT EVALUATION NOTES:**
- **FOCUS ON FINAL RESULT**: The **FINAL RESULT** section contains the agent's actual output, not a summary. This is the most important data for evaluation. If it contains specific, detailed information that answers the task, the agent likely succeeded.
- **DO NOT evaluate for hallucination** - Agent has access to browser_state with the DOM and the screenshot at every step, so trust all factual claims. When the agent provides specific output information in the FINAL RESULT, trust it - the agent has access to the actual page content.
- **Penalize poor planning** - The agent should not use the file system for short tasks.
- **Penalize poor tool usage** - Wrong tools, inefficient approaches, ignoring available information
- **If there is only 1 screenshot available and it's blank but the agent's final result looks accurate and it navigated to the proper website, mark the run as successful with a final score of 70 or higher.


**RESPONSE FORMAT:**
Respond with EXACTLY this JSON structure (no additional text before or after):


{{
   "task_summary": "One sentence summary of what the task was trying to accomplish",
   "reasoning": "Detailed analysis covering: what went well, what didn't work, trajectory quality assessment, tool usage evaluation, output quality review, and overall user satisfaction prediction",
   "error_categories": ["error1", "error2"],
   "final_score": 75,
   "improvement_tips": [
       "Button not clickable: Improve the DOM extraction layer to correctly include buttons in the navigation bar of the website check24.de"
   ]
}}"""

    user_prompt = f"""**TASK:** 
<task>
{task_truncated}
</task>

**FINAL RESULT:**
<agent_final_result>
{final_result_truncated}
</agent_final_result>

**AGENT'S LAST INPUT MESSAGE:**
<agent_last_input_message>
{last_message_truncated}
</agent_last_input_message>

**TOTAL STEPS:** {len(complete_history)}
**SCREENSHOTS PROVIDED:** {len(selected_images)}

Evaluate this agent execution given the criteria and respond with the exact JSON structure requested."""

    content_parts: list[ContentPartTextParam | ContentPartImageParam] = [
        ContentPartTextParam(text=user_prompt)]
    content_parts.extend(encoded_images)

    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        UserMessage(content=content_parts),
    ]

    # Optional debug: print what we send to the model (enable with JUDGE_DEBUG_PROMPT=1)
    if os.getenv("JUDGE_DEBUG_PROMPT"):
        logger.info("[JUDGE DEBUG] System prompt (first 1500 chars):\n%s", system_prompt[:1500])
        # Extract text parts only from user content for readability
        text_parts = []
        for part in content_parts:
            try:
                if getattr(part, 'type', '') == 'text':
                    text_parts.append(getattr(part, 'text', ''))
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        user_text = "\n".join(text_parts)
        logger.info("[JUDGE DEBUG] User prompt text (first 4000 chars):\n%s", user_text[:4000])
        logger.info("[JUDGE DEBUG] Images attached: %d", len(encoded_images))

    try:
        response = await model.invoke(messages, output_format=JudgeResult)
        completion = getattr(response, 'completion', None)
        # If the adapter returned a proper JudgeResult, use it
        if isinstance(completion, JudgeResult):
            return completion
        # If the adapter returned raw text, try to parse JSON and coerce
        if isinstance(completion, str):
            try:
                parsed = json.loads(completion)
                coerced = parse_judge_response(parsed, task)
                return coerced
            except Exception as parse_err:  # pylint: disable=broad-exception-caught
                logger.error(
                    'Failed to parse judge JSON output: %s', parse_err)
                return create_fallback_result(task, 'Judge returned non-JSON output')
        # Unexpected type
        logger.error('Unexpected judge completion type: %s', type(completion))
        return create_fallback_result(task, 'Unexpected judge completion type')
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error('Judge evaluation failed: %s', e)
        return create_fallback_result(task, str(e))


def parse_judge_response(result_dict: dict, task: str) -> JudgeResult:
    """
    Parse raw dictionary response into structured JudgeResult object.

    Converts the JSON response from the LLM judge into a validated JudgeResult,
    handling missing fields and invalid error categories gracefully.

    Args:
        result_dict: Dictionary containing judge evaluation data
        task: Original task description for fallback error messages

    Returns:
        Validated JudgeResult object with parsed data
    """
    try:
        error_categories = []
        if 'error_categories' in result_dict:
            for err in result_dict['error_categories']:
                try:
                    error_categories.append(ErrorCategory(err))
                except ValueError:
                    logger.warning('Unknown error category: %s', err)

        final_score = result_dict.get('final_score', 0)

        return JudgeResult(
            task_summary=result_dict.get(
                'task_summary', 'Task analysis unavailable'),
            reasoning=result_dict.get('reasoning', 'Analysis unavailable'),
            error_categories=error_categories,
            final_score=final_score,
            improvement_tips=result_dict.get('improvement_tips', []),
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error('Failed to parse judge response: %s', e)
        return create_fallback_result(task, 'Failed to parse structured response')


def create_fallback_result(task: str, error_msg: str) -> JudgeResult:
    """
    Create a fallback JudgeResult when evaluation fails.

    Generates a safe default result indicating evaluation failure,
    used when the judge system encounters errors or cannot parse responses.

    Args:
        task: Original task description for context
        error_msg: Error message describing the failure

    Returns:
        JudgeResult indicating evaluation failure with score 0
    """
    return JudgeResult(
        task_summary=f'Failed to analyze task: {task[:100]}...',
        reasoning=f'Evaluation failed: {error_msg}',
        error_categories=[ErrorCategory.IMPOSSIBLE_TASK],
        final_score=0,
        improvement_tips=['Fix evaluation system'],
    )


async def judge_with_retry(
        task: str,
        complete_history: list[dict],
        final_result: str,
        last_message: str,
        screenshot_paths: list[str],
        model: Adapter,
        max_retries: int = 3,
        max_images: int = 10,
) -> JudgeResult:
    """
    Robust judge evaluation with automatic retry logic.

    Wraps the comprehensive_judge function with retry logic to handle
    transient LLM API failures. Uses exponential backoff between retries.

    Args:
        task: Original task description given to the agent
        complete_history: List of agent execution steps with actions and results
        final_result: Agent's final output or result
        last_message: Last message/input provided to the agent
        screenshot_paths: List of screenshot file paths from agent execution
        model: LLM adapter (OpenAI or Gemini) for performing evaluation
        max_retries: Maximum number of retry attempts (default: 3)
        max_images: Maximum number of screenshots to include in evaluation

    Returns:
        JudgeResult from successful evaluation or fallback result on all failures
    """
    for attempt in range(max_retries):
        try:
            return await comprehensive_judge(
                task,
                complete_history,
                final_result,
                last_message,
                screenshot_paths,
                model,
                max_images,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            if attempt == max_retries - 1:
                logger.error('Judge failed after %d attempts: %s',
                             max_retries, e)
                return create_fallback_result(task, str(e))
            logger.warning(
                'Judge attempt %d failed, retrying: %s', attempt+1, e)
            await asyncio.sleep(2**attempt)

    # Should not reach
    return create_fallback_result(task, 'Max retries exceeded without proper error handling')
