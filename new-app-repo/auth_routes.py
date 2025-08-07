from flask import Blueprint, request, jsonify, session
from db import get_db_connection

auth_bp = Blueprint('auth', __name__)

def assign_role_if_not_set(emp_id):
    """
    Checks if an employee has a role and department assigned.
    If not, it analyzes their skills and assigns them a role and department.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Step 1: Fetch the employee's data, including skills and current role/dept
            cursor.execute("SELECT * FROM employee WHERE id = %s", (emp_id,))
            employee = cursor.fetchone()

            # Step 2: Check if department or role is NULL (or empty)
            if not employee or (employee.get('DEPARTMENT') and employee.get('ROLE')):
                # If employee exists and has a role, do nothing.
                if employee:
                    session['role_name'] = employee['ROLE']
                    session['department'] = employee['DEPARTMENT']
                return

            # Step 3: If role is not set, analyze skills to assign one
            # Define skill groups
            frontend_skills = ['HTML', 'CSS', 'JAVASCRIPT']
            backend_skills = ['PYTHON', 'C', 'CPP', 'JAVA']
            testing_skills = ['SQL_TESTING', 'TOOLS_COURSE']

            # Calculate average score for each skill group, handle None values
            frontend_avg = sum(employee.get(skill, 0) or 0 for skill in frontend_skills) / len(frontend_skills)
            backend_avg = sum(employee.get(skill, 0) or 0 for skill in backend_skills) / len(backend_skills)
            testing_avg = sum(employee.get(skill, 0) or 0 for skill in testing_skills) / len(testing_skills)
            
            # Determine the best role
            scores = {
                'Frontend Developer': frontend_avg,
                'Backend Developer': backend_avg,
                'Automation Tester': testing_avg
            }
            
            # Find the role with the maximum average score
            assigned_role = max(scores, key=scores.get)
            
            # Determine department based on role
            if 'Developer' in assigned_role:
                assigned_department = 'Development'
            else:
                assigned_department = 'Testing'

            # Step 4: Update the employee record in the database
            cursor.execute(
                "UPDATE employee SET ROLE = %s, DEPARTMENT = %s WHERE id = %s",
                (assigned_role, assigned_department, emp_id)
            )
            conn.commit()
            
            # Store the newly assigned role and department in the session
            session['role_name'] = assigned_role
            session['department'] = assigned_department

    except Exception as e:
        # In case of an error, rollback changes
        conn.rollback()
        print(f"Error in assign_role_if_not_set: {e}")
    finally:
        conn.close()


@auth_bp.route('/login', methods=['POST'])
def login():
    # Clear any existing session data to ensure a clean login.
    session.clear() 
    
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return {"success": False, "message": "Missing credentials"}, 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Query the credentials table based on the provided SQL dump schema
            cursor.execute(
                "SELECT emp_id, password, is_admin FROM credentials WHERE username = %s LIMIT 1",
                (username,)
            )
            user = cursor.fetchone()

            if user and user['password'] == password:
                # Check if the user is an admin or employee
                if user['is_admin']:
                    session['role'] = 'admin'
                    session['emp_code'] = user['emp_id'] # Using emp_id as the identifier
                else:
                    session['role'] = 'employee'
                    session['emp_code'] = user['emp_id']
                    # NEW: Assign role and department if they don't exist
                    assign_role_if_not_set(user['emp_id'])

                return {"success": True}, 200
            else:
                # No match found or password incorrect
                return {"success": False, "message": "Invalid credentials"}, 401

    finally:
        conn.close()