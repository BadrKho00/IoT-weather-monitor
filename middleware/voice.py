import os
import openai
import tempfile
import sys
import os
sys.path.append(os.path.dirname(__file__))

from bigquery_client import get_historical_data, get_latest_reading, get_daily_averages
from dotenv import load_dotenv

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def speech_to_text(audio_file_path: str) -> str:
    with open(audio_file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text


def text_to_speech(text: str, output_path: str = "response.mp3"):
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    )
    response.stream_to_file(output_path)
    return output_path


def answer_weather_question(question: str) -> str:
    # Gather context from BigQuery
    latest = get_latest_reading()
    daily = get_daily_averages(7)

    context = f"""
    You are a smart home weather assistant. Answer the user's question based on the sensor data below.
    Keep answers short, natural and conversational (2-3 sentences max).

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