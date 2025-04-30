import os
import re
import logging
from docx import Document
from extensions import db
from models import Question

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def clean_text(text):
    """Clean and standardize text for consistent matching."""
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def is_valid_question(text):
    """Check if the text appears to be a valid question."""
    return ("Correct Answer:" in text and 
            any(f"{letter})" in text for letter in ['A', 'B', 'C', 'D']))

def parse_question(text):
    """Parse a question text into its components."""
    try:
        if not is_valid_question(text):
            return None

        # Split into question and answer parts
        parts = text.split('Correct Answer:')
        if len(parts) != 2:
            return None

        question_part = parts[0].strip()
        correct_answer_part = parts[1].strip()

        # Extract just the answer letter (A, B, C, or D)
        correct_option = correct_answer_part[0] if correct_answer_part else ''
        
        # The question text is everything before the first option
        question_text = question_part.split('A)')[0].strip()
        if not question_text:
            return None

        # Extract all options
        options = []
        correct_answer_text = None
        
        # First, try to find option blocks in the format "A) Option text"
        option_matches = re.findall(r'([A-D])\)(.*?)(?=(?:[A-D]\))|(?:Correct Answer)|\Z)', question_part, re.DOTALL)
        
        if len(option_matches) == 4:
            for letter, option_text in option_matches:
                clean_option = clean_text(option_text)
                options.append(clean_option)
                if letter == correct_option:
                    correct_answer_text = clean_option
        else:
            # Fallback to the old method if the regex fails
            for i, letter in enumerate(['A', 'B', 'C', 'D']):
                next_letter_idx = question_part.find(f"{chr(ord(letter)+1)})") if letter != 'D' else len(question_part)
                current_letter_idx = question_part.find(f"{letter})")
                
                if current_letter_idx == -1:
                    return None
                
                if next_letter_idx == -1:
                    next_letter_idx = len(question_part)
                
                option_text = question_part[current_letter_idx+2:next_letter_idx].strip()
                clean_option = clean_text(option_text)
                options.append(clean_option)
                
                if letter == correct_option:
                    correct_answer_text = clean_option

        if len(options) != 4 or not correct_answer_text:
            return None

        return {
            'text': clean_text(question_text),
            'options': options,
            'correct_answer': correct_answer_text,
            'correct_option': correct_option
        }

    except Exception as e:
        logger.error(f"Error parsing question: {str(e)}")
        return None

def import_questions(app):
    """Import questions from the Word document."""
    docx_path = os.path.join(app.root_path, 'WordDoc/citizenship_questions.docx')
    
    with app.app_context():
        try:
            # Keep existing questions, just add new ones if needed
            existing_count = Question.query.count()
            if existing_count > 0:
                logger.info(f"Found {existing_count} existing questions, will add new ones if needed")
            
            # Read Word document
            document = Document(docx_path)
            logger.info(f"Successfully opened document: {docx_path}")

            questions = []
            current_difficulty = "easy"
            
            # Track if a question is state-specific
            state_specific_pattern = re.compile(r'\b([A-Z]{2})\b-specific')

            for para in document.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                # Check difficulty markers
                if "Medium Difficulty Questions" in text:
                    current_difficulty = "medium"
                    continue
                elif "Hard Difficulty Questions" in text:
                    current_difficulty = "hard"
                    continue

                # Skip non-question content
                if any(x in text.lower() for x in ['continue', 'let me know']):
                    continue

                # Check if this is a state-specific question
                state_specific = False
                state = None
                state_match = state_specific_pattern.search(text)
                
                # Handle state-specific questions
                if "[Answer varies by state]" in text or "[Current Governor's Name]" in text or "[State Capital]" in text:
                    state_specific = True
                    state = None
                elif state_match:
                    state_specific = True 
                    state = state_match.group(1)

                # Parse the question
                question_data = parse_question(text)
                if question_data:
                    question_data['difficulty'] = current_difficulty
                    question_data['state_specific'] = state_specific
                    question_data['state'] = state
                    questions.append(question_data)

            if not questions:
                logger.error("No questions were parsed successfully")
                return False

            # Add questions to database
            added_count = 0
            for q in questions:
                try:
                    # Check if this question already exists (by text)
                    existing_question = Question.query.filter_by(text=q['text']).first()
                    if existing_question:
                        continue
                    
                    question = Question(
                        text=q['text'],
                        options=q['options'],
                        correct_answer=q['correct_answer'],
                        difficulty=q['difficulty'],
                        state_specific=q['state_specific'],
                        state=q['state']
                    )
                    db.session.add(question)
                    added_count += 1
                except Exception as e:
                    logger.error(f"Error adding question: {str(e)}")
                    continue

            db.session.commit()
            logger.info(f"Successfully added {added_count} new questions to database")
            
            # Verify counts
            for diff in ['easy', 'medium', 'hard']:
                count = Question.query.filter_by(difficulty=diff).count()
                logger.info(f"Total {diff} questions: {count}")

            return True

        except Exception as e:
            logger.error(f"Error in import_questions: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    from app import app
    import_questions(app)
