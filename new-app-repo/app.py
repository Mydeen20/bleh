from flask import Flask, render_template, session, redirect, request
from flask_cors import CORS
import os
from db import get_db_connection # Import the DB connection function

# Import Blueprints
from auth_routes import auth_bp
from admin_routes import admin_bp
from employee_routes import employee_bp

app = Flask(__name__)

# Secure session key (can be overridden by env variable)
app.secret_key = os.getenv('SECRET_KEY', 'super_secret_key_123')

# Allow cross-origin (for frontend fetch requests)
CORS(app, supports_credentials=True)

# Register route modules
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(employee_bp)


# ---------------- HOME & DASHBOARD ROUTES ----------------

@app.route('/')
def home():
    """Landing page"""
    return render_template('index.html')

# NEW: Central dashboard redirector
@app.route('/dashboard')
def dashboard():
    """Redirects user to the correct dashboard based on their role in the session."""
    if 'role' in session:
        if session['role'] == 'admin':
            return redirect('/dashboard_admin')
        elif session['role'] == 'employee':
            return redirect('/dashboard_employee')
    # If no role or unknown role, send back to login
    return redirect('/')


@app.route('/dashboard_admin')
def dashboard_admin():
    """Admin Dashboard"""
    if session.get('role') == 'admin':
        return render_template('dashboard_admin.html')
    return redirect('/')


@app.route('/dashboard_employee')
def dashboard_employee():
    """Employee Dashboard - Modified to pass employee data"""
    if session.get('role') == 'employee':
        emp_code = session.get('emp_code')
        employee_data = {}
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT NAME, ROLE, DEPARTMENT FROM employee WHERE id = %s", (emp_code,))
                emp = cursor.fetchone()
                if emp:
                    employee_data = {
                        "name": emp.get('NAME', 'Employee'),
                        "role": emp.get('ROLE', 'N/A'),
                        "department": emp.get('DEPARTMENT', 'N/A')
                    }
        finally:
            conn.close()
            
        return render_template('dashboard_employee.html', employee=employee_data)
    return redirect('/')


# ---------------- LOGOUT ----------------

@app.route('/logout', methods=['POST'])
def logout():
    """Clear session and logout user"""
    session.clear()
    return {"success": True, "message": "Logged out"}


# ---------------- ERROR HANDLERS ----------------

@app.errorhandler(404)
def page_not_found(e):
    if session.get('role') == 'admin':
        return redirect('/dashboard_admin')
    elif session.get('role') == 'employee':
        return redirect('/dashboard_employee')
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)