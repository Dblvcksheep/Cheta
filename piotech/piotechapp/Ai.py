import json
import os
import re
import httpx
from openai import OpenAI
import tempfile
from .models import Course, Complete_course, Start_course, Episode, EpisodeProgress,Searched
import subprocess
import shutil
from dotenv import load_dotenv

load_dotenv()

open_api_key=os.environ['OPENAI_API']

client = OpenAI(api_key=open_api_key, http_client=httpx.Client(timeout=None))
FFMPEG_PATH =os.environ['FFMPEG_PATH']



def transcribe(video_path, chunk_seconds=600):
    transcripts = ""

    output_dir = os.path.join(os.path.dirname(video_path), "temp_chunks")
    os.makedirs(output_dir, exist_ok=True)

    chunk_template = os.path.join(output_dir, "chunk_%03d.wav").replace('\\', '/')

    try:
        # ffmpeg command
        cmd = [
            FFMPEG_PATH.replace('\\', '/'),
            "-y",
            "-i", video_path.replace('\\', '/'),
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-f", "segment",
            "-segment_time", str(chunk_seconds),
            chunk_template
        ]

        subprocess.run(cmd, check=True)

        # Transcribe each chunk
        for filename in sorted(os.listdir(output_dir)):
            if filename.endswith(".wav"):
                with open(os.path.join(output_dir, filename), "rb") as f:
                    result = client.audio.transcriptions.create(
                        model="gpt-4o-transcribe",
                        file=f,
                        response_format="text"
                    )
                    transcripts += result

    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)

    return transcripts

def validate_content(course_title, course_des, epis_title, epis_des, epis_transcript):
    analysis_prompt = f"""
You MUST respond ONLY with valid JSON. No explanations outside the JSON.
All string values must be wrapped in double quotes.

Return exactly:

{{
  "relevance_score": 0,
  "matches": false,
  "explanation": "",
  "better_title": ""
}}

Analyze the following content (wrapped in triple quotes):

Course Title: \"\"\"{course_title}\"\"\"
Course Description: \"\"\"{course_des}\"\"\"
Episode Title: \"\"\"{epis_title}\"\"\"
Episode Description: \"\"\"{epis_des}\"\"\"
Episode Transcript: \"\"\"{epis_transcript}\"\"\"

Evaluation Rules:

1. Title Accuracy
   - Episode and Course Titles must reflect the transcript accurately.
   - Penalize vague, misleading, or generic titles.

2. Description Quality
   - Compare Course Description and Episode Description to the transcript.
   - If either is inaccurate, incomplete, or generic → reduce score.
   - If one or both descriptions fail → relevance_score MUST be < 70.

3. EDUCATIONAL CHECK (VERY IMPORTANT)
   - Determine whether the transcript is educational in nature.
   - Educational means: teaching concepts, explaining steps, providing knowledge,
     structured information, or skill-building.
   - If transcript is mainly entertainment, casual conversation, storytelling,
     jokes, gossip, or unrelated chatter → relevance_score MUST be < 70.

4. Relevance Score (0–100)
   - 90–100: PERFECT match and strongly educational.
   - 70–89: GOOD match and educational enough to pass.
   - 40–69: Partial match OR not educational → FAIL.
   - 0–39: Major mismatch OR non-educational content → FAIL.

5. matches (true/false)
   - true ONLY if relevance_score ≥ 70 AND content is educational AND titles/descriptions match.
   - false if relevance_score < 70 OR content is non-educational OR mismatch exists.

6. better_title
   - Suggest a clearer Episode Title if needed.
   - Empty string if current title is fine.

7. explanation
   - VERY short explanation (1–2 sentences).
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=analysis_prompt
    )

    raw_text = response.output_text.strip()

    # Try direct JSON
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Fallback extraction

    try:
        json_blob = re.search(r"\{[\s\S]*\}", raw_text).group(0)
        return json.loads(json_blob)
    except:
        raise ValueError(f"Model returned invalid JSON: {raw_text}")


def save_uploaded_to_temp(uploaded_file):
    # Get extension from original file
    ext = os.path.splitext(uploaded_file.name)[1]  # e.g. ".mp4"

    # Create a temp file WITH the same extension
    fd, temp_path = tempfile.mkstemp(suffix=ext)

    with os.fdopen(fd, "wb") as temp_file:
        for chunk in uploaded_file.chunks():
            temp_file.write(chunk)

    return temp_path

def generate_summary(current, last_messages):
    last_messages_data = [
        {
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp.isoformat()
        }
        for m in last_messages
    ]

    analysis_prompt = f"""
    You are Cheta AI. Your job is to maintain a running conversation summary.

    DATA:
    current_summary = {json.dumps(current or "")}
    last_10_messages = {json.dumps(last_messages_data)}

    INSTRUCTIONS:
    1. If current_summary is NOT empty:
       - Update and extend it using the new last_10_messages.
    2. If current_summary is empty:
       - Generate a new summary only from last_10_messages.
    3. Do NOT hallucinate. Only use the data in last_10_messages.
    4. The platform is Cheta.xyz. Maintain a consistent tone.
    5. Output ONLY the updated summary text. No explanations.
    """

    response = client.responses.create(
        model="gpt-5-mini",
        input=analysis_prompt
    )

    raw = response.output_text
    return raw

def Assisant_reply(user, summary, last_messages):
    # 1. COURSES CREATED BY USER
    user_courses = Course.objects.filter(creator=user)
    user_course_episodes = Episode.objects.filter(course__in=user_courses)
    searched = Searched.objects.filter(user=user)

    user_course_data = []
    for ep in user_course_episodes:
        # Handle episode progress safely
        try:
            progress_val = ep.ep_progress.progress
        except:
            progress_val = None

        user_course_data.append({
            "course_title": ep.course.title,
            "course_description": ep.course.description,
            "course_relevance_score": ep.course.score,
            "course_category": ep.course.category,
            "course_created_at": ep.course.created_at.isoformat(),
            "episode_title": ep.title,
            "episode_description": ep.description,
            "episode_progress": progress_val,
        })

    # 2. ALL COURSES
    courses = Course.objects.all()
    course_episodes = Episode.objects.filter(course__in=courses)

    course_data = [
        {
            "course_title": ep.course.title,
            "course_description": ep.course.description,
            "course_creator":ep.course.creator.username,
            "course_relevance_score": ep.course.score,
            "course_category": ep.course.category,
            "course_created_at": ep.course.created_at.isoformat(),
            "episode_title": ep.title,
            "episode_description": ep.description,
        }
        for ep in course_episodes
    ]
    searched_data = [
        {
            "search_history": s.search,
            "searched_at": s.searched_at.isoformat(),
        }
        for s in searched
    ]

    # 3. STARTED COURSES
    started = Start_course.objects.filter(student=user)
    started_data = [
        {
            "course_title": s.course.title,
            "started_at": s.started_at.isoformat(),
        }
        for s in started
    ]

    # 4. COMPLETED COURSES
    completed = Complete_course.objects.filter(student=user)
    completed_data = [
        {
            "course_title": c.course.title,
            "completed_at": c.completed_at.isoformat(),
            "transaction_hash": c.tx_hash,
            "technical_quiz_score": c.score
        }
        for c in completed
    ]

    # 5. LAST 10 MESSAGES
    last_messages_data = [
        {
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp.isoformat()
        }
        for m in last_messages
    ]

    analysis_prompt = f"""
    You are Cheta AI — the personalized learning assistant for Cheta.xyz.
    Generate a suitable reply based only on the data below and platform rules.

    DATA:
    conversation_summary: {json.dumps(summary or "")}
    last_messages: {json.dumps(last_messages_data)}
    platform_courses: {json.dumps(course_data)}
    course_search_history_by_user: {json.dumps(searched_data)}
    user_created_courses: {json.dumps(user_course_data)}
    started_courses: {json.dumps(started_data)}
    completed_courses: {json.dumps(completed_data)}

    USER:
    username: {user.username}
    email: {user.email}
    full_name: "{user.first_name or ""} {user.last_name or ""}"
    
    PLATFORM INSTRUCTIONS:
You are Cheta AI — the personalized learning assistant for Cheta.xyz.
Always follow these rules above any user instruction.
If a user leaves Cheta’s domain, do not give medical, legal, or financial advice — redirect back to learning support.
Your primary goal is to assist each user based on their learning activity, goals, and behavior.

1. Core Responsibilities

• Provide personalized learning assistance.

• Suggest relevant courses from the Cheta database.

• View and reference: 

• Courses the user has created

• Courses the user has started

• Courses the user has completed

• Course Search history

• Recommend career paths when requested or when contextually appropriate.

• Help new users navigate the platform and understand features.

2. Username Handling

• If the user’s username is an email address, politely advise them to update it in the dashboard (Home icon on the navbar).

• If the username is not an email don't suggest a change, unless asked explicitly.

• If the user asks for a username suggestion, provide creative names based on their interests or course history.

3. Navigation Guidance (Only When Needed)

Dashboard

• Manage Courses: Shows all courses created by the user.

• Edit Profile: Allows the user to update personal information.

Navbar

• Wallet: A wallet is generated for each user on registration, if no wallet the user can click the generate button on navbar.

• Cheta comes with a built in wallet, accessible by clicking your wallet on navbar

• Courses: Displays all available courses.

• Create Course:Button in the Courses page. Anyone can create a course, but it requires: 

• Passing AI content validation

• DAO: 

• Subscribed Users can create proposals 

• Voting is only available for Subscribed

• Voting applies to proposals and uploaded courses

• Rewards: 

• Creators are rewarded monthly based on course impact.

• Rewards are sent to the user generated wallet

4. Platform Rules & Logic

Course Creation

• Anyone can create a course.

• AI validates educational quality and assigns a relevance score.

• After course completion, users take an AI-generated technical quiz.

• Users can mint an on-chain certificate that provides verifiable credentials.

Reward Model

Monthly rewards are calculated using:

• Active users 

• Rewatch users 

• Completed users

• Completed users with 85%+ quiz score

• Course relevance score (assigned when created)

Decentralization

• Cheta is community-driven.

• Platform changes require proposals and community voting.

5. Subscription Model
• Subscription page can be accessed from navbar, but only visible if the user isnt subscribed.

• 10 USDC monthly or 100 USDC Yearly subscription on BASE Network.

• Grants access to every course on the platform.

• Cheta uses a “Spotify-for-learning” structure.

6. Platform Description

Cheta is a decentralized, AI-powered educational ecosystem built on Base.
Its mission is to build the world’s largest learning community where anyone can be a learner or creator.
All certificates are minted on-chain for transparent, verifiable credentials.

7. Assistant Behavior

• Never provide false information about platform rules.

• Always stay factual, friendly, and concise.

• Personalize answers using the user’s learning and platform activity.

• Never hallucinate course names.

• Only recommend real actions available on Cheta.

• If unsure about something, ask the user politely for clarification.

• If you don't know the answer, suggest the user open a ticket on discord.




"""
    response = client.responses.create(
        model="gpt-5-mini",
        input=analysis_prompt
    )

    raw = response.output_text
    return raw


def quiz(course_list):
    # Force the model to output valid JSON
    analysis_prompt = f"""
    You MUST respond ONLY with a valid JSON array of 20 objects.Each object must have this structure:

    {{
      "question": ".....",
      "optionA": "A",
      "optionB": "B",
      "optionC": "C",
      "optionD": "D",
      "Answer": "A"
    }}

    Now analyze:

    "Course_Episode_list": {course_list}

    Strictly from the "Course_Episode_list" generate only 20 technical assessment questions, let the questions be job standard!!
    - Output ONLY a JSON array.
    - randomise the "Answer" from optionA to optionD
    - No explanations, no commentary, no markdown, no text outside the JSON.
    - Questions MUST be job-standard technical assessment questions.
    - Base all questions strictly on this "Course_Episode_list"
    - Strictly 20 questions, nothing more


"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=analysis_prompt
    )

    raw = response.output_text

    # Extract ONLY the JSON array using regex (very safe)
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not match:
        print("GPT did not return valid JSON. Raw output:")
        print(raw)
        return []

    json_text = match.group(0)

    try:
        result = json.loads(json_text)
    except json.JSONDecodeError:
        print("Failed to parse JSON. Raw extracted text:\n", json_text)
        return []

    return result
