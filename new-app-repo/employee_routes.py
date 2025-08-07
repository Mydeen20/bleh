from flask import Blueprint, jsonify, request, session, render_template, redirect
from db import get_db_connection
# We are now using the specific, mark-based recommender agent
from ai_agents import profile_agent, assessment_agent, recommender_agent, tracker_agent, course_recommender_agent_v2
import random

employee_bp = Blueprint('employee', __name__)

# ------------- Page Route for the AI Agent Interface -------------
@employee_bp.route('/employee/agent/<agent_type>')
def agent_page(agent_type):
    """Renders the dedicated page for a specific AI agent."""
    if session.get('role') != 'employee':
        return redirect('/')
    
    valid_agents = ['profile', 'assessment', 'recommender', 'tracker']
    if agent_type not in valid_agents:
        return redirect('/dashboard_employee')

    return render_template('agent_page.html', agent_type=agent_type)


# ------------- API Route for AI Interaction -------------
@employee_bp.route('/ask_agent', methods=['POST'])
def ask_agent():
    if 'role' not in session or session['role'] != 'employee':
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    agent_type = data.get('agent')
    emp_code = session['emp_code']

    agent_functions = {
        'profile': profile_agent,
        'assessment': assessment_agent,
        'recommender': recommender_agent,
        'tracker': tracker_agent
    }

    agent_function = agent_functions.get(agent_type)

    if not agent_function:
        return jsonify({"error": "Unknown agent"}), 400

    response = agent_function(emp_code)
    return jsonify(response)


# ------------- CORRECTED: Course Recommender Route -------------
@employee_bp.route('/employee/recommend_course', methods=['GET'])
def recommend_course():
    """
    This route now correctly calls the AI agent that analyzes employee marks 
    to recommend and assign a new course.
    """
    if session.get('role') != 'employee':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    emp_id = session.get('emp_code')
    
    # This calls the correct function from ai_agents.py
    result = course_recommender_agent_v2(emp_id)
    
    return jsonify(result), 200


# --- ROUTES FOR "MY COURSES" PAGE ---

@employee_bp.route('/employee/my_courses')
def my_courses_page():
    """Renders the page that will display all of the employee's enrolled courses."""
    if session.get('role') != 'employee':
        return redirect('/')
    return render_template('my_courses.html')


@employee_bp.route('/employee/get_my_courses', methods=['GET'])
def get_my_courses():
    """
    MODIFIED: API endpoint now JOINS with the course table to get the CourseFile.
    """
    if session.get('role') != 'employee':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    emp_id = session.get('emp_code')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # UPDATED SQL QUERY to join tables and fetch the course filename
            sql = """
                SELECT
                    ca.course_name,
                    ca.status,
                    ca.progress,
                    c.CourseFile
                FROM
                    course_assigned ca
                JOIN
                    course c ON ca.course_name = c.CourseName
                WHERE
                    ca.emp_id = %s
                ORDER BY
                    ca.assigned_date DESC
            """
            cursor.execute(sql, (emp_id,))
            courses = cursor.fetchall()
        
        return jsonify({"success": True, "courses": courses}), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"An error occurred: {e}"}), 500
    finally:
        conn.close()

# --- ASSESSMENT SUBMISSION ROUTE ---
@employee_bp.route('/employee/submit_assessment', methods=['POST'])
def submit_assessment():
    if session.get('role') != 'employee':
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    emp_id = session.get('emp_code')
    data = request.json
    course_name = data.get('course_name')

    if not course_name:
        return jsonify({"success": False, "message": "Course name not provided."}), 400

    marks = random.randint(1, 10)
    passing_score = 7

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO assessment_marks (emp_id, course_name, marks_obtained) VALUES (%s, %s, %s)",
                (emp_id, course_name, marks)
            )

            if marks >= passing_score:
                cursor.execute(
                    "UPDATE course_assigned SET status = 'Completed', progress = 100 WHERE emp_id = %s AND course_name = %s",
                    (emp_id, course_name)
                )
                message = f"Congratulations! You passed with a score of {marks}/10."
                passed = True
            else:
                cursor.execute(
                    "UPDATE course_assigned SET progress = 0, status = 'In Progress' WHERE emp_id = %s AND course_name = %s",
                    (emp_id, course_name)
                )
                message = f"You scored {marks}/10, which is below the passing mark of {passing_score}. Please review the material and try the assessment again."
                passed = False

            conn.commit()
            return jsonify({"success": True, "passed": passed, "score": marks, "message": message})

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"An error occurred: {e}"}), 500
    finally:
        conn.close()