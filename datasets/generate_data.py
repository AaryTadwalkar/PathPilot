import json
import os
import shutil

domains = [
    "Python", "Machine Learning", "Deep Learning", "Web Development", "Backend Development",
    "Data Science", "Cloud Computing", "DevOps", "Cybersecurity", "Mobile Development",
    "UI/UX Design", "Database Engineering"
]

courses = []
course_id = 1
for domain in domains:
    for i in range(5):
        courses.append({
            "id": f"C{course_id:03d}",
            "title": f"Complete {domain} Course {i+1}",
            "provider": "Coursera" if i % 2 == 0 else "Udemy",
            "url": f"https://example.com/course/C{course_id:03d}",
            "level": "Beginner" if i < 2 else ("Intermediate" if i < 4 else "Advanced"),
            "duration_hours": 10 + i * 5,
            "topics": [domain, f"{domain} Basics", f"Advanced {domain}"],
            "skills_taught": [domain],
            "prerequisites": ["None"] if i == 0 else [f"{domain} Basics"],
            "domain": domain,
            "rating": 4.5 + (i % 5) * 0.1,
            "description": f"Learn {domain} from scratch. This is course {i+1}.",
            "is_free": i == 0
        })
        course_id += 1

base_dir = r"c:\Users\Aary\OneDrive\Desktop\Alumni_plugins-module-1\datasets"
os.makedirs(base_dir, exist_ok=True)

with open(os.path.join(base_dir, "courses_catalog.json"), "w") as f:
    json.dump(courses, f, indent=2)

goals = []
for i in range(20):
    goals.append({
        "id": f"G{i+1:03d}",
        "name": f"Master {domains[i % len(domains)]}",
        "description": f"Become an expert in {domains[i % len(domains)]}",
        "keywords": [domains[i % len(domains)], "Expert", "Master"],
        "required_skills": [domains[i % len(domains)]],
        "recommended_course_ids": [f"C{(i % len(domains)) * 5 + j + 1:03d}" for j in range(3)],
        "difficulty": "Hard",
        "estimated_weeks": 12
    })

with open(os.path.join(base_dir, "learning_goals.json"), "w") as f:
    json.dump({"goals": goals}, f, indent=2)

# Delete files
files_to_delete = [
    r"c:\Users\Aary\OneDrive\Desktop\Alumni_plugins-module-1\backend\ingest_webdev_jobs.py",
    r"c:\Users\Aary\OneDrive\Desktop\Alumni_plugins-module-1\backend\migrate_prs.py",
    r"c:\Users\Aary\OneDrive\Desktop\Alumni_plugins-module-1\backend\migrate_career.py",
    r"c:\Users\Aary\OneDrive\Desktop\Alumni_plugins-module-1\backend\reset_db.py"
]

for file in files_to_delete:
    try:
        if os.path.exists(file):
            os.remove(file)
            print(f"Deleted {file}")
    except Exception as e:
        print(f"Error deleting {file}: {e}")
