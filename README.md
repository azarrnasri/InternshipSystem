# InternshipSystem
SEF ASSIGNMENT

# Internship Placement System

This Django project manages internship placements with full UI, logbooks, evaluations, and notifications.

## Setup and Run

1. Open GitHub Desktop → File → Clone repository.  
2. Select the repository from GitHub.com and choose a local path → click **Clone**.  
3. Open the cloned folder in **Visual Studio Code** and open a terminal from there.  
4. Create a virtual environment: `python -m venv venv`  
5. Activate the virtual environment: `venv\Scripts\activate.bat`  
6. Install required packages: `pip install -r requirements.txt`  
7. Apply migrations: `python manage.py migrate`  
8. Run the server: `python manage.py runserver` → open browser at `http://127.0.0.1:8000/`  
9. Deactivate virtual environment when done: `deactivate`  

USER INFORMATION
username pass
std1     1234 (student)
cpy1     1234 (company advisor)
acd      1234 (academic advisor)

**Notes:**  
- `venv/` is **not included** in the repository; each collaborator must create their own.  
- Static files for the GUI are included inside app folders.  
- `.gitignore` ensures temporary files, logs, and virtual environment are **not tracked**.
