import os
import sys
import openai
import tempfile

sys.path.append(os.path.dirname(__file__))

from bigquery_client import get_historical_data, get_latest_reading, get_daily_averages
from dotenv import load_dotenv

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def speech_to_text(audio_file_path: str) -> str:
    """Convert an audio file to text using OpenAI Whisper"""
    with open(audio_file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text


def text_to_speech(text: str, output_path: str = "response.mp3"):
    """Convert text to an audio file using OpenAI TTS"""
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    )
    response.stream_to_file(output_path)
    return output_path


def answer_weather_question(question: str) -> str:
    """Answer a weather question using BigQuery data and GPT-4o"""
    latest = get_latest_reading()
    daily = get_daily_averages(7)

    context = f"""
    You are a smart weather assistant for a football/soccer coach in Lausanne, Switzerland.
    Your job is to help the coach make decisions about training sessions based on weather
    and indoor conditions. Answer questions in 2-3 sentences, naturally and concisely.

    Current readings:
    - Indoor temperature: {latest.get('temperature_indoor')}°C
    - Indoor humidity: {latest.get('humidity_indoor')}%
    - Air quality index: {latest.get('air_quality')}
    - Outdoor temperature: {latest.get('temperature_outdoor')}°C
    - Weather: {latest.get('weather_description')}
    - Wind speed: {latest.get('wind_speed')} m/s

    7-day daily averages:
    {daily.to_string() if not daily.empty else 'No historical data yet'}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": context},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content


def process_voice_query(audio_file_path: str) -> dict:
    """Full pipeline: audio file → transcribe → answer → audio response"""
    question = speech_to_text(audio_file_path)
    print(f"Question heard: {question}")

    answer = answer_weather_question(question)
    print(f"Answer: {answer}")

    audio_response_path = text_to_speech(answer)

    return {
        "question": question,
        "answer": answer,
        "audio_path": audio_response_path
    }