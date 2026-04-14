import json
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.font import Font
import hashlib
import os
import cv2
import face_recognition
import pickle
import geocoder

THEME_COLOR = "#0066cc"     
BG_COLOR = "#ffffff"        
ACCENT_COLOR = "#00aa55"   
ERROR_COLOR = "#dc3545"     
TEXT_COLOR = "#212529"      
HOVER_COLOR = "#0056b3"     
SECONDARY_BG = "#f8f9fa"    

class CustomButton(tk.Button):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.default_bg = kwargs.get('bg', THEME_COLOR)
        self.default_fg = kwargs.get('fg', 'white')
        
        self.configure(
            relief=tk.FLAT,
            borderwidth=0,
            padx=15,
            pady=8,
            font=("Segoe UI", 10),
            cursor="hand2",
            activebackground=HOVER_COLOR,
            activeforeground="white"
        )
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
    
    def on_enter(self, e):
        self['bg'] = HOVER_COLOR
    
    def on_leave(self, e):
        self['bg'] = self.default_bg

class ModernFrame(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        
        style = ttk.Style()
        style.configure('Modern.TFrame', background=BG_COLOR)
        style.configure('Secondary.TFrame', background=SECONDARY_BG)
        
        style.configure('Modern.TEntry',
                       fieldbackground=BG_COLOR,
                       borderwidth=1,
                       relief=tk.SOLID)
        
        style.configure('Modern.TLabel',
                       background=BG_COLOR,
                       foreground=TEXT_COLOR,
                       font=("Segoe UI", 10))
        
        style.configure('Modern.Treeview',
                       background=BG_COLOR,
                       foreground=TEXT_COLOR,
                       rowheight=25,
                       fieldbackground=BG_COLOR)
        style.configure('Modern.Treeview.Heading',
                       background=SECONDARY_BG,
                       foreground=TEXT_COLOR,
                       font=("Segoe UI", 10, "bold"))
        
        self.configure(style='Modern.TFrame')

class AttendanceTracker:
    def __init__(self):
        if not os.path.exists('database'):
            os.makedirs('database')
        
        self.conn = sqlite3.connect('database/attendance_tracker.db')
        self.create_tables()
        
        self.create_default_warden()

    def create_default_warden(self):
        try:
            cursor = self.conn.execute('SELECT COUNT(*) FROM users WHERE role = "warden"')
            if cursor.fetchone()[0] == 0:
                username = "warden"
                password = "warden123"  # Default password
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                self.conn.execute('''
                INSERT INTO users (username, password, role) VALUES (?, ?, ?)
                ''', (username, hashed_password, "warden"))
                self.conn.commit()
        except sqlite3.OperationalError:
            pass

    def create_tables(self):
        try:
            self.conn.execute('''CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_number TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
                room TEXT,
                hostel_location TEXT,
                face_encoding BLOB
            )''')
   
            self.conn.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment_number TEXT NOT NULL,
            date TEXT NOT NULL,
                FOREIGN KEY (enrollment_number) REFERENCES students(enrollment_number)
            )''')

            self.conn.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                enrollment_number TEXT,
                FOREIGN KEY (enrollment_number) REFERENCES students(enrollment_number)
            )''')
            
            self.conn.commit()
            self.create_default_warden()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            raise

    def register_user(self, username, password, role, enrollment_number=None):
        if not username or not password or not role:
            return False
            
        try:
            cursor = self.conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', (username,))
            if cursor.fetchone()[0] > 0:
                return False

            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            self.conn.execute('INSERT INTO users (username, password, role, enrollment_number) VALUES (?, ?, ?, ?)',
                            (username, hashed_password, role, enrollment_number))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Registration error: {e}")
            if self.conn:
                self.conn.rollback()
            return False

    def authenticate_user(self, username, password):
        try:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            cursor = self.conn.execute('''
            SELECT role, enrollment_number FROM users WHERE username = ? AND password = ?
            ''', (username, hashed_password))
            result = cursor.fetchone()
            return result if result else None
        except sqlite3.Error as e:
            print(f"Authentication error: {e}")
            return None

    def register_student(self, enrollment_number, name, room, hostel_location, face_encoding):
        try:
            face_encoding_bytes = pickle.dumps(face_encoding)
            
            self.conn.execute('''
            INSERT INTO students (enrollment_number, name, room, hostel_location, face_encoding) 
            VALUES (?, ?, ?, ?, ?)
            ''', (enrollment_number, name, room, hostel_location, sqlite3.Binary(face_encoding_bytes)))
            self.conn.commit()
            return f"Student {name} registered successfully in room {room}."
        except sqlite3.IntegrityError:
            return "Enrollment Number already exists."
        except Exception as e:
            return f"Registration failed: {str(e)}"

    def mark_attendance(self, enrollment_number):
        date = datetime.now().strftime("%Y-%m-%d")
        self.conn.execute('''
        INSERT INTO attendance (enrollment_number, date) VALUES (?, ?)
        ''', (enrollment_number, date))
        self.conn.commit()
        return f"Attendance marked for enrollment number {enrollment_number} on {date}."

    def view_attendance(self, enrollment_number):
        cursor = self.conn.execute('''
        SELECT date FROM attendance WHERE enrollment_number = ?
        ''', (enrollment_number,))
        records = cursor.fetchall()
        if records:
            return f"Attendance records for enrollment number {enrollment_number}:\n" + "\n".join([record[0] for record in records])
        else:
            return "No attendance records found."

    def view_all_students(self):
        try:
            cursor = self.conn.execute('''
            SELECT enrollment_number, name, room 
            FROM students 
            ORDER BY enrollment_number
            ''')
            students = cursor.fetchall()
            return students
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch student details: {str(e)}")
            return None

    def delete_student(self, enrollment_number):
        if not enrollment_number:
            return False
            
        try:
            self.conn.execute('DELETE FROM users WHERE enrollment_number = ?', (enrollment_number,))
            self.conn.execute('DELETE FROM students WHERE enrollment_number = ?', (enrollment_number,))
            self.conn.commit()
            return True
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            messagebox.showerror("Error", f"Failed to delete student: {str(e)}")
            return False

    def close_connection(self):
        self.conn.close()

    def get_current_location(self):
        try:
            g = geocoder.ip('me')
            if g.ok:
                return g.address
            else:
                return None
        except Exception as e:
            print(f"Error getting location: {e}")
            return None

class LoginWindow:
    def __init__(self, root, tracker):
        self.root = root
        self.tracker = tracker
        self.root.title("Login - Attendance System")
        self.root.geometry("400x580")
        self.root.configure(bg=BG_COLOR)

        main_frame = ModernFrame(root, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_font = Font(family="Segoe UI", size=24, weight="bold")
        title_label = ttk.Label(main_frame, 
                              text="Welcome",
                              font=title_font,
                              foreground=THEME_COLOR,
                              style='Modern.TLabel')
        title_label.pack(pady=(0, 5))

        subtitle_font = Font(family="Segoe UI", size=11)
        subtitle_label = ttk.Label(main_frame,
                                 text="Sign in to continue",
                                 font=subtitle_font,
                                 foreground=TEXT_COLOR,
                                 style='Modern.TLabel')
        subtitle_label.pack(pady=(0, 30))

        form_frame = ModernFrame(main_frame)
        form_frame.pack(fill=tk.X, pady=10)

        ttk.Label(form_frame, 
                 text="Username",
                 font=("Segoe UI", 10),
                 style='Modern.TLabel').pack(anchor=tk.W)
        
        self.username_entry = ttk.Entry(form_frame,
                                      font=("Segoe UI", 11),
                                      style='Modern.TEntry')
        self.username_entry.pack(fill=tk.X, pady=(5, 15))

        ttk.Label(form_frame, 
                 text="Password",
                 font=("Segoe UI", 10),
                 style='Modern.TLabel').pack(anchor=tk.W)
        
        self.password_entry = ttk.Entry(form_frame,
                                      font=("Segoe UI", 11),
                                      show="•",
                                      style='Modern.TEntry')
        self.password_entry.pack(fill=tk.X, pady=(5, 15))

        ttk.Label(form_frame, 
                 text="Select Role",
                 font=("Segoe UI", 10),
                 style='Modern.TLabel').pack(anchor=tk.W)
        
        self.role_var = tk.StringVar(value="student")
        
        roles_frame = ModernFrame(form_frame)
        roles_frame.pack(fill=tk.X, pady=(5, 20))
        
        style = ttk.Style()
        style.configure('Modern.TRadiobutton',
                       background=BG_COLOR,
                       font=("Segoe UI", 10))
        
        ttk.Radiobutton(roles_frame,
                       text="Student",
                       variable=self.role_var,
                       value="student",
                       style='Modern.TRadiobutton').pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Radiobutton(roles_frame,
                       text="Warden",
                       variable=self.role_var,
                       value="warden",
                       style='Modern.TRadiobutton').pack(side=tk.LEFT)

        button_frame = ModernFrame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)

        login_button = CustomButton(button_frame,
                                  text="Sign In",
                                  command=self.login,
                                  bg=THEME_COLOR,
                                  fg="white")
        login_button.pack(fill=tk.X, pady=(0, 10))

        signup_button = CustomButton(button_frame,
                                   text="Create Account",
                                   command=self.show_signup,
                                   bg=ACCENT_COLOR,
                                   fg="white")
        signup_button.pack(fill=tk.X)

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        role = self.role_var.get()

        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return

        try:
            result = self.tracker.authenticate_user(username, password)
            if result:
                user_role, enrollment_number = result
                if user_role == role:
                    self.root.destroy()
                    root = tk.Tk()
                    app = AttendanceApp(root, self.tracker, user_role, enrollment_number)
                    root.mainloop()
                else:
                    messagebox.showerror("Error", "Invalid role selected")
            else:
                messagebox.showerror("Error", "Invalid username or password")
        except Exception as e:
            messagebox.showerror("Error", f"Login failed: {str(e)}")

    def show_signup(self):
        signup_window = tk.Toplevel(self.root)
        signup_window.title("Sign Up")
        signup_window.geometry("400x400")
        signup_window.configure(bg="#f0f0f0")

        main_frame = ttk.Frame(signup_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Username:").pack(anchor=tk.W)
        username_entry = ttk.Entry(main_frame)
        username_entry.pack(fill=tk.X, pady=5)

        ttk.Label(main_frame, text="Password:").pack(anchor=tk.W)
        password_entry = ttk.Entry(main_frame, show="*")
        password_entry.pack(fill=tk.X, pady=5)

        ttk.Label(main_frame, text="Confirm Password:").pack(anchor=tk.W)
        confirm_password_entry = ttk.Entry(main_frame, show="*")
        confirm_password_entry.pack(fill=tk.X, pady=5)

        ttk.Label(main_frame, text="Role:").pack(anchor=tk.W)
        role_var = tk.StringVar(value="student")
        ttk.Radiobutton(main_frame, text="Student", variable=role_var, value="student").pack(anchor=tk.W)
        ttk.Radiobutton(main_frame, text="Warden", variable=role_var, value="warden").pack(anchor=tk.W)

        ttk.Label(main_frame, text="Enrollment Number (for students only):").pack(anchor=tk.W)
        enrollment_number_entry = ttk.Entry(main_frame)
        enrollment_number_entry.pack(fill=tk.X, pady=5)

        def signup():
            username = username_entry.get()
            password = password_entry.get()
            confirm_password = confirm_password_entry.get()
            role = role_var.get()
            enrollment_number = enrollment_number_entry.get() if role == "student" else None

            if not username or not password:
                messagebox.showerror("Error", "Please fill in all required fields")
                return

            if password != confirm_password:
                messagebox.showerror("Error", "Passwords do not match")
                return

            if role == "student" and not enrollment_number:
                messagebox.showerror("Error", "Enrollment Number is required for student accounts")
                return

            try:
                if self.tracker.register_user(username, password, role, enrollment_number):
                    messagebox.showinfo("Success", "Account created successfully")
                    signup_window.destroy()
                else:
                    messagebox.showerror("Error", "Username already exists")
            except Exception as e:
                messagebox.showerror("Error", f"Signup failed: {str(e)}")

        signup_button = tk.Button(main_frame,
                                text="Sign Up",
                                command=signup,
                                bg="#2E7D32",
                                fg="white",
                                font=("Helvetica", 10, "bold"),
                                padx=20,
                                pady=10)
        signup_button.pack(pady=20)

class AttendanceApp:
    def __init__(self, root, tracker, role, enrollment_number=None):
        self.tracker = tracker
        self.role = role
        self.enrollment_number = enrollment_number
        self.root = root
        self.root.title("Hostel Attendance System")
        self.root.geometry("800x700")
        self.root.configure(bg=BG_COLOR)

        top_frame = ModernFrame(root)
        top_frame.pack(fill=tk.X, padx=20, pady=10)
        
        back_button = CustomButton(top_frame,
                                 text="← Back",
                                 command=self.go_back_to_login,
                                 bg=THEME_COLOR,
                                 fg="white")
        back_button.pack(side=tk.LEFT)
        
        role_label = ttk.Label(top_frame,
                             text=f"Logged in as {role.capitalize()}",
                             font=("Helvetica", 10),
                             foreground=TEXT_COLOR)
        role_label.pack(side=tk.RIGHT, pady=5)

        content_frame = ModernFrame(root, padding="30")
        content_frame.pack(fill=tk.BOTH, expand=True)

        header_frame = ModernFrame(content_frame)
        header_frame.pack(fill=tk.X, pady=(0, 30))
        
        title_font = Font(family="Helvetica", size=24, weight="bold")
        welcome_label = ttk.Label(header_frame,
                                text=f"Welcome to Your Dashboard",
                                font=title_font,
                                foreground=THEME_COLOR)
        welcome_label.pack(anchor=tk.W)
        
        subtitle_font = Font(family="Helvetica", size=12)
        subtitle_label = ttk.Label(header_frame,
                                 text="Manage attendance and student records with ease",
                                 font=subtitle_font,
                                 foreground=TEXT_COLOR)
        subtitle_label.pack(anchor=tk.W)

        button_frame = ModernFrame(content_frame)
        button_frame.pack(fill=tk.BOTH, expand=True)
        
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        row = 0
        if role == "warden":
            register_btn = CustomButton(button_frame,
                                     text="Register New Student",
                                     command=self.register_student,
                                     bg=THEME_COLOR,
                                     fg="white")
            register_btn.grid(row=row, column=0, padx=10, pady=10, sticky="ew")
            
            view_btn = CustomButton(button_frame,
                                  text="View All Students",
                                  command=self.view_all_students,
                                  bg=THEME_COLOR,
                                  fg="white")
            view_btn.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
            row += 1

        if role == "student":
            mark_btn = CustomButton(button_frame,
                                  text="Mark Today's Attendance",
                                  command=self.mark_attendance,
                                  bg=ACCENT_COLOR,
                                  fg="white")
            mark_btn.grid(row=row, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
            row += 1

        view_attendance_btn = CustomButton(button_frame,
                                         text="View Attendance Records",
                                         command=self.view_attendance,
                                         bg=THEME_COLOR,
                                         fg="white")
        view_attendance_btn.grid(row=row, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        self.status_bar = ttk.Label(root,
                                  text="Ready",
                                  relief=tk.FLAT,
                                  anchor=tk.W,
                                  padding=10,
                                  background=THEME_COLOR,
                                  foreground="white",
                                  font=("Helvetica", 10))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def go_back_to_login(self):
        # Close the database connection
        self.tracker.close_connection()
        
        # Destroy current window
        self.root.destroy()
        
        # Create new login window
        root = tk.Tk()
        tracker = AttendanceTracker()  # Create a new tracker instance
        login_window = LoginWindow(root, tracker)
        root.mainloop()

    def register_student(self):
        register_window = tk.Toplevel(self.root)
        register_window.title("Register Student")
        register_window.geometry("400x600")
        register_window.configure(bg="#f0f0f0")
        
        main_frame = ttk.Frame(register_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_font = Font(family="Helvetica", size=16, weight="bold")
        title_label = ttk.Label(main_frame, 
                              text="Register New Student",
                              font=title_font,
                              padding=10,
                              foreground="#2E7D32")
        title_label.pack(pady=10)
        
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ttk.Label(form_frame, text="Enrollment Number:", font=("Helvetica", 10)).pack(anchor=tk.W, pady=5)
        enrollment_entry = ttk.Entry(form_frame, font=("Helvetica", 10))
        enrollment_entry.pack(fill=tk.X, pady=5)
        
        ttk.Label(form_frame, text="Full Name:", font=("Helvetica", 10)).pack(anchor=tk.W, pady=5)
        name_entry = ttk.Entry(form_frame, font=("Helvetica", 10))
        name_entry.pack(fill=tk.X, pady=5)
        
        ttk.Label(form_frame, text="Room Number:", font=("Helvetica", 10)).pack(anchor=tk.W, pady=5)
        room_entry = ttk.Entry(form_frame, font=("Helvetica", 10))
        room_entry.pack(fill=tk.X, pady=5)
        
        location_status = ttk.Label(form_frame, 
                                  text="Getting location...",
                                  font=("Helvetica", 10),
                                  foreground="blue")
        location_status.pack(pady=5)
        
        current_location = self.get_current_location()
        if current_location:
            location_status.config(text=f"Location detected: {current_location}", foreground="green")
        else:
            location_status.config(text="Failed to detect location", foreground="red")
            messagebox.showerror("Error", "Could not detect location. Please check your internet connection.")
            return
        
        face_capture_button = tk.Button(form_frame,
                                      text="Capture Face",
                                      command=lambda: self.capture_face(face_status_label),
                                      bg="#2E7D32",
                                      fg="white",
                                      font=("Helvetica", 10, "bold"),
                                      padx=20,
                                      pady=10)
        face_capture_button.pack(pady=10)
        
        face_status_label = ttk.Label(form_frame, 
                                    text="Face not captured",
                                    font=("Helvetica", 10),
                                    foreground="red")
        face_status_label.pack(pady=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        def submit_registration():
            enrollment_number = enrollment_entry.get().strip()
            name = name_entry.get().strip()
            room = room_entry.get().strip()
            
            if not enrollment_number or not name or not room:
                messagebox.showerror("Error", "All fields are required")
                return
                
            if not hasattr(self, 'face_encoding'):
                messagebox.showerror("Error", "Please capture face before registering")
                return
                
            message = self.tracker.register_student(enrollment_number, name, room, current_location, self.face_encoding)
            if "successfully" in message:
                messagebox.showinfo("Success", message)
                register_window.destroy()
                self.status_bar.config(text=f"Student {name} registered successfully")
            else:
                messagebox.showerror("Error", message)
        
        submit_button = tk.Button(button_frame,
                                text="Register",
                                command=submit_registration,
                                bg="#2E7D32",
                                fg="white",
                                font=("Helvetica", 10, "bold"),
                                padx=20,
                                pady=10)
        submit_button.pack(side=tk.LEFT, padx=10)
        
        cancel_button = tk.Button(button_frame,
                                text="Cancel",
                                command=register_window.destroy,
                                bg="#d32f2f",
                                fg="white",
                                font=("Helvetica", 10, "bold"),
                                padx=20,
                                pady=10)
        cancel_button.pack(side=tk.RIGHT, padx=10)

    def capture_face(self, status_label):
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                messagebox.showerror("Error", "Could not open camera")
                return
            
            cv2.namedWindow("Face Capture", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Face Capture", 640, 480)
            
            face_detected = False
            face_encoding = None
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                face_locations = face_recognition.face_locations(rgb_frame)
                
                if face_locations:
                    top, right, bottom, left = face_locations[0]
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    
                    face_encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
                    face_detected = True
                
                cv2.imshow("Face Capture", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            
            if face_detected and face_encoding is not None:
                self.face_encoding = face_encoding
                status_label.config(text="Face captured successfully", foreground="green")
            else:
                messagebox.showerror("Error", "No face detected. Please try again.")
                status_label.config(text="Face not captured", foreground="red")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to capture face: {str(e)}")
            status_label.config(text="Face not captured", foreground="red")

    def mark_attendance(self):
        if self.role == "student":
            try:
                current_location = self.get_current_location()
                if not current_location:
                    messagebox.showerror("Error", "Could not detect location. Please check your internet connection.")
                    return
                
                cursor = self.tracker.conn.execute('''
                SELECT hostel_location, face_encoding 
                FROM students 
                WHERE enrollment_number = ?
                ''', (self.enrollment_number,))
                student_data = cursor.fetchone()
                
                if not student_data:
                    messagebox.showerror("Error", f"Student with enrollment number {self.enrollment_number} not found in database")
                    return
                
                registered_location = student_data[0]
                stored_face_encoding = student_data[1]
                
                if not stored_face_encoding:
                    messagebox.showerror("Error", "No face data found for this student. Please register your face first.")
                    return
                
                if current_location.lower() != registered_location.lower():
                    messagebox.showerror("Error", 
                                       f"Location mismatch!\nCurrent: {current_location}\nRegistered: {registered_location}")
                    return
                
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    messagebox.showerror("Error", "Could not open camera")
                    return
                
                cv2.namedWindow("Face Verification", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("Face Verification", 640, 480)
                
                face_verified = False
                
                try:
                    stored_encoding = pickle.loads(bytes(stored_face_encoding))
                except Exception as e:
                    print(f"Error loading face data: {e}")
                    messagebox.showerror("Error", "Failed to load stored face data. Please register your face again.")
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    face_locations = face_recognition.face_locations(rgb_frame)
                    
                    if face_locations:
                        top, right, bottom, left = face_locations[0]
                        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        
                        current_face_encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
                        
                        matches = face_recognition.compare_faces([stored_encoding], current_face_encoding)
                        if matches[0]:
                            face_verified = True
                            cv2.putText(frame, "Face Verified", (left, top - 10),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            break
                        else:
                            cv2.putText(frame, "Face Not Recognized", (left, top - 10),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    cv2.imshow("Face Verification", frame)
                    
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                
                cap.release()
                cv2.destroyAllWindows()
                
                if face_verified:
                    try:
                        date = datetime.now().strftime("%Y-%m-%d")
                        cursor = self.tracker.conn.execute('''
                        SELECT COUNT(*) FROM attendance 
                        WHERE enrollment_number = ? AND date = ?
                        ''', (self.enrollment_number, date))
                        already_marked = cursor.fetchone()[0] > 0
                        
                        if already_marked:
                            messagebox.showinfo("Info", "Attendance already marked for today!")
                            return
                        
                        self.tracker.conn.execute('''
                        INSERT INTO attendance (enrollment_number, date) 
                        VALUES (?, ?)
                        ''', (self.enrollment_number, date))
                        self.tracker.conn.commit()
                        messagebox.showinfo("Success", "Attendance marked successfully!")
                        self.status_bar.config(text=f"Attendance marked for student {self.enrollment_number}")
                    except sqlite3.Error as e:
                        messagebox.showerror("Database Error", f"Failed to mark attendance: {str(e)}")
                        self.tracker.conn.rollback()
                else:
                    messagebox.showerror("Error", "Face verification failed. Please try again.")
                
            except Exception as e:
                print(f"Attendance marking error: {e}")  # Add debug print
                messagebox.showerror("Error", f"Failed to mark attendance: {str(e)}")
                self.status_bar.config(text="Failed to mark attendance")
                try:
                    cap.release()
                    cv2.destroyAllWindows()
                except:
                    pass

    def view_attendance(self):
        enrollment_number = simpledialog.askstring("View Attendance", "Enter Enrollment Number to view attendance:")
        if enrollment_number:
            message = self.tracker.view_attendance(enrollment_number)
            self.show_records_window(f"Attendance Records - Enrollment Number: {enrollment_number}", message)
            self.status_bar.config(text=f"Viewing attendance for student {enrollment_number}")

    def show_records_window(self, title, records):
        records_window = tk.Toplevel(self.root)
        records_window.title(title)
        records_window.geometry("600x400")
        records_window.configure(bg="#f0f0f0")

        main_frame = ttk.Frame(records_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(text_frame, 
                            wrap=tk.WORD,
                            font=("Helvetica", 10),
                            yscrollcommand=scrollbar.set,
                            bg="white",
                            padx=10,
                            pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        text_widget.insert(tk.END, records)
        text_widget.config(state=tk.DISABLED)  # Make it read-only

        close_button = tk.Button(main_frame,
                               text="Close",
                               command=records_window.destroy,
                               bg="#2E7D32",
                               fg="white",
                               font=("Helvetica", 10, "bold"),
                               padx=20,
                               pady=10)
        close_button.pack(pady=10)

    def view_all_students(self):
        students = self.tracker.view_all_students()
        if not students:
            messagebox.showinfo("Student Details", "No students registered yet.")
            return
            
        student_window = tk.Toplevel(self.root)
        student_window.title("All Student Details")
        student_window.geometry("800x600")
        student_window.configure(bg="#f0f0f0")
        
        main_frame = ttk.Frame(student_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_font = Font(family="Helvetica", size=16, weight="bold")
        title_label = ttk.Label(main_frame, 
                              text="Student Details",
                              font=title_font,
                              padding=10,
                              foreground="#2E7D32")
        title_label.pack(pady=10)
        
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll = ttk.Scrollbar(table_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("enrollment", "name", "room")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", 
                          yscrollcommand=tree_scroll.set)
        
        tree.heading("enrollment", text="Enrollment Number")
        tree.heading("name", text="Name")
        tree.heading("room", text="Room")
        
        tree.column("enrollment", width=150)
        tree.column("name", width=200)
        tree.column("room", width=100)
        
        for student in students:
            tree.insert("", tk.END, values=student)
        
        tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=tree.yview)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        delete_button = tk.Button(button_frame,
                                text="Delete Selected Student",
                                command=lambda: self.delete_selected_student(tree, student_window),
                                bg="#d32f2f",
                                fg="white",
                                font=("Helvetica", 10, "bold"),
                                padx=20,
                                pady=10)
        delete_button.pack(side=tk.LEFT, padx=10)
        
        close_button = tk.Button(button_frame,
                               text="Close",
                               command=student_window.destroy,
                               bg="#2E7D32",
                               fg="white",
                               font=("Helvetica", 10, "bold"),
                               padx=20,
                               pady=10)
        close_button.pack(side=tk.RIGHT, padx=10)

    def delete_selected_student(self, tree, window):
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a student to delete")
            return
            
        values = tree.item(selected_item)['values']
        enrollment_number = values[0]
        name = values[1]
        
        if messagebox.askyesno("Confirm Delete", 
                             f"Are you sure you want to delete student {name} (Enrollment: {enrollment_number})?\nThis action cannot be undone."):
            if self.tracker.delete_student(enrollment_number):
                messagebox.showinfo("Success", f"Student {name} has been deleted successfully")
                tree.delete(selected_item)
            else:
                messagebox.showerror("Error", "Failed to delete student")

    def close(self):
        self.tracker.close_connection()
        self.root.quit()

    def get_current_location(self):
        try:
            g = geocoder.ip('me')
            if g.ok:
                return g.address
            else:
                return None
        except Exception as e:
            print(f"Error getting location: {e}")
            return None

if __name__ == "__main__":
    root = tk.Tk()
    tracker = AttendanceTracker()
    login_window = LoginWindow(root, tracker)
    root.mainloop()
