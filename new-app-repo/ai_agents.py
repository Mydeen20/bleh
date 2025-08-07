import os
from langchain_google_genai import ChatGoogleGenerativeAI
import pandas as pd
from db import get_db_connection

# Use your Gemini API Key (set as environment variable)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")

# Initialize the LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.3
)

def call_ai(prompt: str):
    """Utility function to call the AI model and clean the response."""
    try:
        response = llm.invoke(prompt)
        # Clean the text: remove backticks, quotes, and leading/trailing whitespace
        clean_text = response.content.strip().replace("```", "").replace('"', '').replace("'", "")
        return clean_text
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- NEW: Fully functional version for the company_roles schema ---
def hr_agent_process_file(df: pd.DataFrame):
    """
    Processes a DataFrame from an uploaded file to add new employees.
    It adds records to the 'employee' and 'credentials' tables.
    The role and department are left NULL to be assigned on first login.

    Expected file columns: NAME, HTML, CSS, JAVASCRIPT, PYTHON, C, CPP, JAVA, SQL_TESTING, TOOLS_COURSE
    """
    conn = get_db_connection()
    employees_added = 0
    
    # Standardize column names from the uploaded file
    df.columns = [col.strip().upper() for col in df.columns]
    
    # Define the columns we expect for skills and employee name
    expected_cols = ['NAME', 'HTML', 'CSS', 'JAVASCRIPT', 'PYTHON', 'C', 'CPP', 'JAVA', 'SQL_TESTING', 'TOOLS_COURSE']
    
    if 'NAME' not in df.columns:
        return 0, "File is missing the required 'NAME' column."

    try:
        with conn.cursor() as cursor:
            for _, row in df.iterrows():
                employee_name = row['NAME']
                
                # Prepare skill data for insertion, defaulting to 0 if a column is missing
                skill_values = {col: row.get(col, 0) for col in expected_cols if col != 'NAME'}
                
                # Build the SQL query dynamically
                cols = ", ".join(skill_values.keys())
                placeholders = ", ".join(["%s"] * len(skill_values))
                
                # Insert into employee table
                sql_employee = f"INSERT INTO employee (NAME, {cols}) VALUES (%s, {placeholders})"
                cursor.execute(sql_employee, (employee_name, *skill_values.values()))
                
                # Get the ID of the new employee
                new_emp_id = cursor.lastrowid
                
                # Generate default credentials
                username = f"{employee_name.lower().split()[0]}{new_emp_id}"
                password = f"pass{new_emp_id}"
                email = f"{username}@company.com"
                
                # Insert into credentials table
                sql_credentials = "INSERT INTO credentials (emp_id, username, password, email, is_admin) VALUES (%s, %s, %s, %s, 0)"
                cursor.execute(sql_credentials, (new_emp_id, username, password, email))
                
                employees_added += 1
        
        conn.commit()
        return employees_added, None

    except Exception as e:
        conn.rollback()
        return 0, str(e)
    finally:
        conn.close()

# --- NEW: Fully functional version for the company_roles schema ---
def generate_employee_analysis_agent(emp_id: int):
    """
    Fetches an employee's skills from the 'employee' table, analyzes them, 
    and generates an AI-powered upskilling roadmap.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get employee's details and all skill scores
            cursor.execute("SELECT * FROM employee WHERE id = %s", (emp_id,))
            employee = cursor.fetchone()
            if not employee:
                return None, None, None, "Employee not found."

        # Define skill columns and extract them from the employee record
        skill_columns = ['HTML', 'CSS', 'JAVASCRIPT', 'PYTHON', 'C', 'CPP', 'JAVA', 'SQL_TESTING', 'TOOLS_COURSE']
        skills = {skill: employee.get(skill, 0) or 0 for skill in skill_columns}
        
        # Analyze skills to find top 3 and weakest 3
        # Filter out skills with 0 score to not count them as weak
        non_zero_skills = {k: v for k, v in skills.items() if v > 0}
        if not non_zero_skills:
            return employee, {}, {}, "No proficiency data found for this employee."

        sorted_skills = sorted(non_zero_skills.items(), key=lambda x: x[1], reverse=True)
        top_skills = dict(sorted_skills[:3])
        weak_skills = dict(sorted_skills[-3:])

        # Employee details for the prompt
        employee_details = {
            "Name": employee.get('NAME'),
            "Domain": employee.get('DEPARTMENT'),
            "Role": employee.get('ROLE')
        }

        # Generate the AI analysis prompt
        prompt = f"""
        You are an expert AI Career Development Analyst for a corporate Learning Management System.
        Your task is to provide a concise, actionable, and encouraging upskilling roadmap for an employee.

        Employee Name: {employee_details['Name']}
        Employee Domain: {employee_details['Domain']}
        Employee Role: {employee_details['Role']}
        Full Skill Profile (Score out of 100): {skills}
        Identified Top 3 Skills: {top_skills}
        Identified Weakest 3 Skills: {weak_skills}

        Based on this data, please generate a report with the following structure using markdown:

        **Overall Summary:**
        (Provide a brief 2-3 sentence summary of the employee's current skill set in relation to their role and domain.)

        **Key Strengths:**
        (List the top skills and briefly explain why they are valuable for their role.)

        **Recommended Upskilling Roadmap:**
        (Provide a bulleted list of 3-4 clear, actionable steps. Focus on improving the weakest skills first, but also suggest how they can leverage their strengths. Be specific and suggest types of projects or learning paths.)

        **Concluding Remark:**
        (End with a short, encouraging sentence.)
        """
        
        analysis_text = call_ai(prompt)
        
        return employee_details, top_skills, weak_skills, analysis_text

    except Exception as e:
        return None, None, None, f"An error occurred during analysis: {e}"
    finally:
        if conn and conn.open:
            conn.close()


# ----------- AI Course Recommender Agent (Based on Skills) -----------
def course_recommender_agent_v2(emp_id: int):
    """
    Analyzes an employee's skills, finds the weakest one, and uses an AI to 
    recommend a specific course. The recommended course is then stored in the
    database.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Step 1: Fetch employee skills and role
            cursor.execute("SELECT * FROM employee WHERE id = %s", (emp_id,))
            employee = cursor.fetchone()
            if not employee:
                return {"success": False, "message": "Employee not found."}

            # Step 2: Identify all skill columns and find the weakest one
            skill_columns = ['HTML', 'CSS', 'JAVASCRIPT', 'PYTHON', 'C', 'CPP', 'JAVA', 'SQL_TESTING', 'TOOLS_COURSE']
            skills = {skill: employee.get(skill, 0) or 0 for skill in skill_columns}
            
            weakest_skill = min(skills, key=skills.get)
            employee_role = employee.get('ROLE', 'Trainee')

            # Step 3: Generate a prompt for the AI
            prompt = f"""
            As a corporate Learning Management System AI, your task is to recommend one specific, actionable course title for an employee based on their weakest skill.

            Employee Role: {employee_role}
            Employee Skill Scores (out of 100): {skills}
            Identified Weakest Skill: {weakest_skill}

            Based on this data, suggest a single course title to help the employee improve their weakest skill. The title should be concise and sound like a real course.

            Examples: "Advanced JavaScript for Developers", "Mastering Python Data Structures", "Introduction to UI/UX with Figma".

            Return only the course title and nothing else.
            """
            
            # Step 4: Call the AI to get the course name
            recommended_course_name = call_ai(prompt)

            if "AI Error" in recommended_course_name:
                 return {"success": False, "message": recommended_course_name}
            
            # Step 5: Store the recommended course in the new 'course_assigned' table
            cursor.execute(
                "SELECT * FROM course_assigned WHERE emp_id = %s AND course_name = %s AND status != 'Completed'",
                (emp_id, recommended_course_name)
            )
            if cursor.fetchone():
                return {"success": True, "course": {"CourseName": recommended_course_name, "message": "This course is already assigned to you."}}

            cursor.execute(
                "INSERT INTO course_assigned (emp_id, course_name, status, progress) VALUES (%s, %s, 'Not Started', 0)",
                (emp_id, recommended_course_name)
            )
            conn.commit()

            return {"success": True, "course": {"CourseName": recommended_course_name}}

    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()

# ----------- Existing Employee-Facing Agents -----------
def profile_agent(emp_code: str):
    """Generates a profile summary for an employee."""
    prompt = f"You are an AI profile assistant. Analyze employee {emp_code} and give a summary of their current learning profile in 2-3 sentences, followed by key strengths and areas to improve."
    output = call_ai(prompt)
    return {
        "agent": "Profile Agent",
        "summary": "Here is a quick overview of your profile:",
        "details": [line.strip() for line in output.split('.') if line.strip()]
    }

def assessment_agent(emp_code: str):
    """Provides an assessment status for an employee."""
    prompt = f"You are an AI assessment agent. Check the assessment status for employee {emp_code}. Provide pending and completed assessments with short recommendations."
    output = call_ai(prompt)
    return {
        "agent": "Assessment Agent",
        "summary": "Here is your assessment progress:",
        "details": [line.strip() for line in output.split('.') if line.strip()]
    }

def recommender_agent(emp_code: str):
    """Recommends new courses for an employee."""
    prompt = f"You are a course recommendation AI. Suggest 3-5 courses that employee {emp_code} should take next based on skill gaps and learning history."
    output = call_ai(prompt)
    return {
        "agent": "Recommender Agent",
        "summary": "Based on your profile, these courses are recommended:",
        "details": [line.strip() for line in output.split('.') if line.strip()]
    }

def tracker_agent(emp_code: str):
    """Summarizes an employee's learning progress."""
    prompt = f"You are a learning progress tracker. Summarize the current progress for employee {emp_code}, including learning percentage, completed modules, and remaining steps."
    output = call_ai(prompt)
    return {
        "agent": "Tracker Agent",
        "summary": "Here is your current learning progress:",
        "details": [line.strip() for line in output.split('.') if line.strip()]
    }