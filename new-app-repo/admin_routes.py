from flask import Blueprint, request, jsonify, session, render_template, Response, redirect, url_for
from db import get_db_connection
from ai_agents import hr_agent_process_file, generate_employee_analysis_agent
import csv
from io import StringIO
import os
import pandas as pd
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__)

# ------------- PAGE ROUTES -------------

@admin_bp.route('/admin/ai_report/<emp_code>')
def ai_report_page(emp_code):
    if session.get('role') != 'admin':
        return redirect('/')
    
    employee_id = int(emp_code)
    employee, top_skills, weak_skills, analysis = generate_employee_analysis_agent(employee_id)

    if not employee:
        return "Employee not found", 404

    return render_template(
        'admin_ai_report.html',
        employee=employee,
        top_skills=top_skills,
        weak_skills=weak_skills,
        analysis=analysis
    )

@admin_bp.route('/admin/hr_agent')
def hr_agent_page():
    if session.get('role') == 'admin':
        return render_template('admin_hr_agent.html')
    return redirect('/')

@admin_bp.route('/admin/agent_metrics_page')
def agent_metrics_page():
    if session.get('role') == 'admin':
        return render_template('admin_agent_metrics.html')
    return redirect('/')

@admin_bp.route('/admin/generate_reports_page')
def generate_reports_page():
    if session.get('role') == 'admin':
        return render_template('admin_generate_reports.html')
    return redirect('/')

@admin_bp.route('/admin/add_employee_page')
def add_employee_page():
    if session.get('role') == 'admin':
        return render_template('admin_add_employee.html')
    return redirect('/')

@admin_bp.route('/admin/delete_employee_page')
def delete_employee_page():
    if session.get('role') == 'admin':
        return render_template('admin_delete_employee.html')
    return redirect('/')

@admin_bp.route('/admin/show_employees')
def show_employees_page():
    if session.get('role') == 'admin':
        return render_template('admin_show_employees.html')
    return redirect('/')

@admin_bp.route('/admin/search_filters')
def search_filters_page():
    if session.get('role') == 'admin':
        return render_template('admin_search_filters.html')
    return redirect('/')

# ------------- API ROUTES -------------

# ----------- AI HR Agent File Upload Logic -----------
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'json'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@admin_bp.route('/admin/hr_agent/upload_employees', methods=['POST'])
def upload_employees_by_agent():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"success": False, "message": "Invalid or no selected file"}), 400
        
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    try:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.csv': df = pd.read_csv(filepath)
        elif ext == '.xlsx': df = pd.read_excel(filepath)
        elif ext == '.json': df = pd.read_json(filepath)
        else: raise ValueError("Unsupported file format")
    except Exception as e:
        os.remove(filepath)
        return jsonify({"success": False, "message": f"Error reading file: {e}"}), 500

    employees_added, error = hr_agent_process_file(df)
    
    os.remove(filepath)

    if error:
        return jsonify({"success": False, "message": f"Error processing data: {error}"}), 500
        
    return jsonify({"success": True, "message": f"AI HR Agent successfully onboarded {employees_added} new employees."}), 200

# ----------- Employee Data Endpoints -----------
@admin_bp.route('/admin/list_employees', methods=['GET'])
def list_employees():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, NAME, DEPARTMENT, ROLE FROM employee")
            employees = cursor.fetchall()
        return jsonify({"success": True, "employees": employees}), 200
    finally:
        conn.close()

@admin_bp.route('/admin/search_employees', methods=['GET'])
def search_employees():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    department = request.args.get('department', '')
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT id, NAME, DEPARTMENT, ROLE FROM employee WHERE 1=1"
            params = []
            
            if department:
                query += " AND DEPARTMENT LIKE %s"
                params.append(f"%{department}%")
            
            cursor.execute(query, params)
            employees = cursor.fetchall()
        
        return jsonify({"success": True, "employees": employees}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

# ----------- Dashboard & Report Endpoints -----------
@admin_bp.route('/admin/dashboard_stats', methods=['GET'])
def dashboard_stats():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DEPARTMENT, COUNT(*) as count FROM employee GROUP BY DEPARTMENT")
            progress_by_dept = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) as total_employees FROM employee")
            total_employees = cursor.fetchone()['total_employees']
        chart_data = {
            "labels": [dept['DEPARTMENT'] for dept in progress_by_dept if dept['DEPARTMENT']],
            "data": [dept['count'] for dept in progress_by_dept if dept['DEPARTMENT']]
        }
        stats = {"total_employees": total_employees, "learning_progress_chart": chart_data}
        return jsonify({"success": True, "stats": stats}), 200
    finally:
        conn.close()

@admin_bp.route('/admin/agent_metrics', methods=['GET'])
def agent_metrics():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    metrics = {
        "profile_agent": {"queue": 3, "latency_ms": 120, "error_rate": "2%"},
        "assessment_agent": {"queue": 5, "latency_ms": 200, "error_rate": "0.5%"},
        "recommender_agent": {"queue": 2, "latency_ms": 150, "error_rate": "1%"},
        "tracker_agent": {"queue": 0, "latency_ms": 80, "error_rate": "0%"}
    }
    return jsonify({"success": True, "metrics": metrics}), 200

@admin_bp.route('/admin/generate_report', methods=['GET'])
def generate_report():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    report_type = request.args.get('type', 'all')
    target = request.args.get('target', '')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT * FROM employee"
            params = []
            if report_type == 'department' and target:
                query += " WHERE DEPARTMENT = %s"
                params.append(target)
            elif report_type == 'individual' and target:
                query += " WHERE id = %s"
                params.append(target)

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        if not rows:
            return "No records found for this report.", 404
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={"Content-Disposition": f"attachment; filename={report_type}_report.csv"})
    finally:
        conn.close()

# --- UPDATED: API ROUTE TO ADD A SINGLE EMPLOYEE WITH MARKS ---
@admin_bp.route('/admin/add_employee', methods=['POST'])
def add_employee():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.json
    name = data.get('Name')
    password = data.get('Password')
    
    if not all([name, password]):
        return jsonify({"success": False, "error": "Name and Password are required."}), 400

    # Extract marks for all subjects, defaulting to 0 if not provided
    marks = {
        "HTML": data.get('HTML', 0),
        "CSS": data.get('CSS', 0),
        "JAVASCRIPT": data.get('JAVASCRIPT', 0),
        "PYTHON": data.get('PYTHON', 0),
        "JAVA": data.get('JAVA', 0),
        "C": data.get('C', 0),
        "CPP": data.get('CPP', 0),
        "SQL_TESTING": data.get('SQL_TESTING', 0),
        "TOOLS_COURSE": data.get('TOOLS_COURSE', 0)
    }

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Insert into the employee table with name and all marks.
            # Role and Department are left NULL to be assigned on first login.
            sql = """
                INSERT INTO employee 
                (NAME, HTML, CSS, JAVASCRIPT, PYTHON, JAVA, C, CPP, SQL_TESTING, TOOLS_COURSE)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (name, marks['HTML'], marks['CSS'], marks['JAVASCRIPT'], marks['PYTHON'],
                      marks['JAVA'], marks['C'], marks['CPP'], marks['SQL_TESTING'], marks['TOOLS_COURSE'])
            
            cursor.execute(sql, params)
            new_emp_id = cursor.lastrowid

            # Create default credentials
            username = f"{name.lower().replace(' ', '')}{new_emp_id}"
            email = f"{username}@company.com"
            cursor.execute(
                "INSERT INTO credentials (emp_id, username, password, email, is_admin) VALUES (%s, %s, %s, %s, 0)",
                (new_emp_id, username, password, email)
            )
        conn.commit()
        return jsonify({"success": True, "message": "Employee added successfully!"}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

@admin_bp.route('/admin/delete_employee', methods=['POST'])
def delete_employee():
    if session.get('role') != 'admin':
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.json
    emp_id = data.get('Emp_Code')

    if not emp_id:
        return jsonify({"success": False, "error": "Employee ID is required."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            result = cursor.execute("DELETE FROM employee WHERE id = %s", (emp_id,))
            
        conn.commit()

        if result > 0:
            return jsonify({"success": True, "message": "Employee deleted successfully."}), 200
        else:
            return jsonify({"success": False, "error": "Employee not found."}), 404
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()