from fastapi import FastAPI, UploadFile, Form, Depends, HTTPException
from PyPDF2 import PdfReader
from docx import Document
import openai
import os
from loguru import logger as logging
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from . import models
# Set up OpenAI API key
openai.api_key = os.environ['OPENAI_KEY']

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    return "".join(page.extract_text() for page in reader.pages)

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join(paragraph.text for paragraph in doc.paragraphs)


# Initialize global variable to track question count
question_count = 0
def generate_question(resume_text, previous_answer=None):
    """
    Generate an interview question in a conversational and human-like manner.
    
    Args:
        resume_text (str): The extracted text from the resume.
        previous_answer (str): The answer to the previous question (optional).
    
    Returns:
        str: A generated interview question.
    """
    global question_count
    question_count += 1  # Increment question count

    # Define a conversational tone and style
    if question_count == 1:
        prompt = "Start the interview with a friendly and general question to make the candidate feel comfortable. Avoid anything technical."
    elif question_count == 2:
        prompt = "Ask a general question about their career or background, keeping it light and conversational."
    else:
        prompt = "Begin transitioning into slightly more specific questions related to their experience and resume."

    # Construct the messages for the chat model
    messages = [
        {"role": "system", "content": "You are an expert interviewer conducting a conversational and friendly interview."},
        {
            "role": "user",
            "content": f"""
            Please generate a single, conversational, and human-like interview question.
            - {prompt}
            - Speak naturally, as if you're sitting across the candidate in a real interview.
            - Base the question loosely on the resume content if applicable, but avoid being overly technical or scripted.
            - If a previous answer is provided, consider following up naturally on it.
            
            Resume Content:
            {resume_text}
            
            {f"Previous Answer: {previous_answer}" if previous_answer else ""}
            """
        }
    ]
    
    # Call OpenAI Chat API to generate a question
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Replace with "gpt-4" if needed
        messages=messages,
        max_tokens=50,
        temperature=0.8,  # Slightly increase creativity for varied questions
        frequency_penalty=0.2,
        presence_penalty=0.3,
    )
    
    # Prepend question number to the generated question
    question = response['choices'][0]['message']['content'].strip()
    logging.error(f"questiin: {f"Question {question_count}: {question}"}")
    return f"Question {question_count}: {question}"


def analyze_answer(user_answer: str) -> int:
    """
    Analyzes the user's answer using OpenAI API and assigns a score between 1 and 5.
    
    Args:
        user_answer (str): The answer provided by the user.
        
    Returns:
        int: A score between 1 (poor) and 5 (excellent).
    """
    try:
        # Define the prompt to analyze the user's answer
        prompt = (
            "Analyze the following answer and rate it on a scale from 1 to 5, "
            "where 1 is very poor and 5 is excellent. Consider clarity, relevance, "
            "and detail in the answer. Respond with just the number (1-5).\n\n"
            f"User's Answer: {user_answer}\n\n"
            "Score (1-5):"
        )

        # Call the OpenAI API using the "gpt-4-mini" model
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini-2024-07-18",  # Changed to gpt-4-mini
            messages=[ 
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,  # Increase max tokens to capture the score
            temperature=0.3,
        )

        logging.error(f"response: {response}")
        # Extract the score from the response
        score = int(response['choices'][0]['message']['content'].strip())
        
        # Ensure the score is within the valid range
        if 1 <= score <= 5:
            return score
        else:
            raise ValueError(f"Invalid score received from OpenAI: {score}")
    except Exception as e:
        # Handle exceptions and fallback to a default score
        logging.error(f"Error in analyze_answer: {e}")
        return 3  # Default score in case of an error


def generate_answer(question: str) -> str:
    """
    Generates a concise answer (2-3 lines) for the given question using OpenAI API.
    
    Args:
        question (str): The question to generate an answer for.
        
    Returns:
        str: A generated answer (2-3 lines).
    """
    try:
        # Define the prompt to generate a concise answer
        prompt = (
            "Provide a concise and clear answer (2-3 lines) to the following question:\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )

        # Call the OpenAI API using the correct endpoint for chat-based models
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Or "gpt-4" if available
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,  # Limit tokens to ensure short answers
            temperature=0.5,
        )

        logging.error(f"response in generate_answer: {response}")
        # Extract the answer from the response
        generated_answer = response['choices'][0]['message']['content'].strip()

        # Return the generated answer
        return generated_answer
    except Exception as e:
        # Handle exceptions and fallback to a default answer
        logging.error(f"Error in generate_answer: {e}")
        return "Sorry, I couldn't generate an answer at the moment. Please try again later."
    

# Settings
SESSION_TIMEOUT_MINUTES = 30


# Function to handle session timeouts
def enforce_session_timeout(session_id: int, db: Session):
    try:
        # Fetch the session from the database
        session = db.query(models.Session).filter(models.Session.id == session_id, models.Session.is_active == True).first()
        if not session:
            logging.info(f"Session {session_id} is already inactive or does not exist.")
            return

        # Check if the session has timed out
        timeout_threshold = session.start_time + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        if datetime.utcnow() >= timeout_threshold:
            session.is_active = False
            session.end_time = datetime.utcnow()
            db.commit()
            logging.info(f"Session {session_id} timed out and has been ended.")
    except Exception as e:
        logging.error(f"Error in enforce_session_timeout: {e}")
