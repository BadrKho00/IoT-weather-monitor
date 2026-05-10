import os
import sys
import openai

sys.path.append(os.path.dirname(__file__))

from bigquery_client import get_historical_data, get_latest_reading, get_daily_averages
from announcements import check_announcements, get_demo_announcement
from dotenv import load_dotenv

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Tracks the last time a motion-triggered announcement was made
# Stored in memory — resets when Flask restarts (acceptable behavior)
_last_motion_announcement = None


def speech_to_text(audio_file_path: str) -> str:
    """
    Convert an audio file to text using OpenAI Whisper.
    The coach speaks into the device and this transcribes it.
    """
    with open(audio_file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text


def text_to_speech(text: str, output_path: str = "response.mp3") -> str:
    """
    Convert text to an audio file using OpenAI TTS.
    The device speaks the announcement or answer out loud.
    """
    response = client.audio.speech.create(
        model="tts-1",
        voice="onyx",   # onyx sounds authoritative - good for a coach assistant
        input=text
    )
    response.stream_to_file(output_path)
    return output_path


def answer_weather_question(question: str) -> str:
    """
    Answer a weather or training-related question using BigQuery data and GPT-4o.
    The coach can ask things like:
    - 'Was it safe to train outside yesterday?'
    - 'What was the humidity in the locker room this morning?'
    - 'Should I plan training for this afternoon?'
    """
    latest = get_latest_reading()
    daily = get_daily_averages(7)

    system_prompt = f"""
    You are a professional weather assistant for a football coach based in Lausanne, Switzerland.
    Your job is to help the coach make smart decisions about training sessions based on
    current weather conditions, indoor locker room conditions, and historical data.

    Always be direct and practical. Give concrete recommendations, not vague answers.
    Keep responses to 2-3 sentences maximum - the coach is busy.
    Use coaching language: pitch, players, warm-up, drills, hydration, intensity.

    Current conditions:
    - Indoor (locker room) temperature: {latest.get('temperature_indoor')}°C
    - Indoor humidity: {latest.get('humidity_indoor')}%
    - Air quality index (AQI): {latest.get('air_quality')} (safe below 100, poor above 150)
    - Outdoor (pitch) temperature: {latest.get('temperature_outdoor')}°C
    - Weather: {latest.get('weather_description')}
    - Wind speed: {latest.get('wind_speed')} m/s

    7-day historical averages:
    {daily.to_string() if not daily.empty else 'No historical data available yet.'}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content


def process_voice_query(audio_file_path: str) -> dict:
    """
    Full voice pipeline: audio in -> transcribe -> answer -> audio out.
    Used when the coach speaks a question into the device.
    """
    question = speech_to_text(audio_file_path)
    print(f"Coach asked: {question}")

    answer = answer_weather_question(question)
    print(f"Assistant answered: {answer}")

    audio_response_path = text_to_speech(answer)

    return {
        "question": question,
        "answer": answer,
        "audio_path": audio_response_path
    }


def run_announcements(sensor_data: dict, forecast: list, motion_detected: bool = False) -> list:
    """
    Check all 6 announcement rules and speak any that trigger.
    Called by the M5Stack when motion is detected or on a schedule.

    Returns list of announcements that were triggered (for logging).
    """
    global _last_motion_announcement
    from datetime import datetime

    triggered = check_announcements(
        sensor_data=sensor_data,
        forecast=forecast,
        motion_detected=motion_detected,
        last_announcement_time=_last_motion_announcement
    )

    for message in triggered:
        print(f"Announcing: {message}")
        audio_path = text_to_speech(message)
        if motion_detected:
            _last_motion_announcement = datetime.now()

    return triggered


def run_demo_announcement(rule_number: int, sensor_data: dict) -> dict:
    """
    Force a specific announcement for live demo/defense purposes.
    Called via the /demo-announce Flask endpoint.
    """
    message = get_demo_announcement(rule_number, sensor_data)
    print(f"DEMO announcement rule {rule_number}: {message}")
    audio_path = text_to_speech(message, output_path=f"demo_rule_{rule_number}.mp3")

    return {
        "rule": rule_number,
        "message": message,
        "audio_path": audio_path
    }