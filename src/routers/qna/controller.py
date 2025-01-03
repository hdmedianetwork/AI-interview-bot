from fastapi import FastAPI, UploadFile, Form, Depends, HTTPException
from PyPDF2 import PdfReader
from docx import Document
import openai
import os
from loguru import logger as logging
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from . import models

import smtplib  # For sending emails
from email.mime.text import MIMEText


# Set up OpenAI API key
openai.api_key = os.environ['OPENAI_KEY']
SECRET_KEY =  os.environ['SECRET_KEY']

def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    return "".join(page.extract_text() for page in reader.pages)

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join(paragraph.text for paragraph in doc.paragraphs)


def generate_question(job_title, job_description, resume_text, session_id, db: Session, previous_answer=None):
    """
    Generate an interview question in a conversational and human-like manner.

    Args:
        job_title (str): The job title from the resume.
        job_description (str): The job description from the resume.
        resume_text (str): The extracted text from the resume.
        session_id (int): The ID of the current session.
        db (Session): The database session to fetch existing questions.
        previous_answer (str): The answer to the previous question (optional).

    Returns:
        str: A generated interview question.
    """
    # Fetch the number of questions already asked in the current session
    existing_questions_count = (
        db.query(models.QnA)
        .filter(models.QnA.session_id == session_id)
        .count()
    )

    # Determine the current question number
    question_count = existing_questions_count + 1

    # Define the style and focus of the question
    if question_count == 1:
        prompt = f"Start with a friendly question to break the ice, based on their job title: {job_title}."
    elif question_count == 2:
        prompt = f"Ask about their experience in the role: {job_title}. Use details from the job description: {job_description}."
    else:
        prompt = "Focus on their skills, accomplishments, or notable projects mentioned in their resume."

    # Prepare messages for the OpenAI chat model
    messages = [
        {"role": "system", "content": "You are an expert interviewer conducting a friendly and engaging interview."},
        {
            "role": "user",
            "content": f"""
            Generate a concise and conversational interview question:
            - Context: Resume details, job title ({job_title}), and job description ({job_description}).
            - Resume Content: {resume_text}
            {f"- Follow up based on the previous answer: {previous_answer}" if previous_answer else ""}
            {prompt}
            """
        },
    ]
    # Call OpenAI Chat API
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # The same model as in the original code
        messages=messages,
        max_tokens=80,  # Limit to 80 tokens to ensure concise output
        temperature=0.8,  # Allow creativity while staying relevant
        frequency_penalty=0.2,
        presence_penalty=0.3,
    )

    # Extract and format the generated question
    question = response['choices'][0]['message']['content'].strip()
    logging.info(f"Generated question: {question}")
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

# Utility function to send email
def send_email(to_email: str, subject: str, message: str):
    try:
        sender_email = os.environ['EMAIL'] # Replace with your email
        sender_password = os.environ['APP_PASSWORD']       # Replace with your email password

        # Create the email
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email

        # Connect to the server and send the email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:  # Adjust for your email provider
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
    except Exception as e:
        print(f"Failed to send email: {e}")


def generate_token(interview_id: int):
    payload = {
        "interview_id": interview_id,
        "exp": datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def validate_token(token: str, interview_id: int):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["interview_id"] == interview_id
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False