import streamlit as st
import pdfplumber
import pymysql
import os
import re
import pandas as pd
from datetime import datetime, date, time, timedelta
from dotenv import load_dotenv
import docx2txt

# Load environment variables
load_dotenv()

# Database configuration
db_config = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "hari006"),
    "database": os.getenv("MYSQL_DATABASE", "document_db")
}

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def get_db_connection():
    try:
        conn = pymysql.connect(**db_config)
        return conn
    except pymysql.Error as e:
        st.error(f"Failed to connect to MySQL: {e}")
        return None

def create_documents_table():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                extracted_text TEXT,
                extracted_tables TEXT,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id VARCHAR(50) NOT NULL
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

def create_file_content_table():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_content (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                extracted_text TEXT COLLATE utf8mb4_unicode_ci,
                user_id VARCHAR(50) NOT NULL,
                upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

def create_log_details_table():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                mobile VARCHAR(10) NOT NULL,
                email VARCHAR(100) NOT NULL,
                address TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

def create_admins_table():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                admin_id VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("SELECT admin_id FROM admins WHERE admin_id = %s", ("admin",))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO admins (admin_id, password) VALUES (%s, %s)", ("admin", "admin123"))
        conn.commit()
        cursor.close()
        conn.close()

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_mobile(mobile):
    pattern = r'^\d{10}$'
    return re.match(pattern, mobile) is not None

def is_valid_filename(filename):
    if not (filename.lower().endswith('.pdf') or filename.lower().endswith('.docx')):
        return False
    pattern = r'^[a-zA-Z0-9_\-\s]+\.(pdf|docx)$'
    return re.match(pattern, filename) is not None

def register_admin(admin_id, password):
    if not all([admin_id, password]):
        st.error("All fields are required.")
        return False
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT admin_id FROM admins WHERE admin_id = %s", (admin_id,))
            if cursor.fetchone():
                st.error("Admin ID already exists.")
                return False
            cursor.execute("INSERT INTO admins (admin_id, password) VALUES (%s, %s)", (admin_id, password))
            conn.commit()
            st.success("Admin registration successful!")
            return True
        except Exception as e:
            st.error(f"Registration failed: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def authenticate_admin(admin_id, password):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT admin_id FROM admins WHERE admin_id = %s AND password = %s", (admin_id, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        if admin:
            st.session_state.admin_id = admin[0]
            return True
    return False

def extract_content_from_pdf(pdf_file, filename):
    try:
        text = ""
        tables = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
                page_tables = page.extract_tables()
                for table in page_tables:
                    table_str = "\n".join(["\t".join(map(str, row)) for row in table])
                    tables.append(table_str)
        tables_combined = "\n\n".join(tables) if tables else ""
        return text, tables_combined
    except Exception as e:
        st.error(f"Failed to extract content from {filename}: {e}")
        return "", ""

def extract_content_from_docx(docx_file, filename):
    try:
        text = docx2txt.process(docx_file)
        return text, ""
    except Exception as e:
        st.error(f"Failed to extract content from {filename}: {e}")
        return "", ""

def normalize_text(text):
    if not text:
        return ""
    # Normalize line endings to \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text

def store_document_content(filename, text, tables, user_id):
    # Normalize the extracted text before storing
    normalized_text = normalize_text(text)
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Store in documents table
            cursor.execute("""
                INSERT INTO documents (filename, extracted_text, extracted_tables, user_id)
                VALUES (%s, %s, %s, %s)
            """, (filename, normalized_text, tables, user_id))
            
            # Store in file_content table
            cursor.execute("""
                INSERT INTO file_content (filename, extracted_text, user_id, upload_time)
                VALUES (%s, %s, %s, %s)
            """, (filename, normalized_text, user_id, datetime.now()))
            
            conn.commit()
            st.success(f"Content from {filename} stored successfully!")
            return True
        except pymysql.Error as e:
            st.error(f"Failed to store content: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    else:
        st.error("Failed to connect to the database while storing document content.")
    return False

def admin_upload_page():
    st.title("Upload Documents")
    if not st.session_state.get("admin_id"):
        st.error("Please log in as admin.")
        st.session_state.page = "admin_login"
        st.rerun()
        return

    uploaded_files = st.file_uploader("Choose PDF or DOCX files", type=["pdf", "docx"], accept_multiple_files=True)
    
    if uploaded_files:
        st.write("### Confirm Filenames")
        confirmed_files = []
        
        if "admin_confirmed_filenames" not in st.session_state:
            st.session_state.admin_confirmed_filenames = {}

        for uploaded_file in uploaded_files:
            original_filename = uploaded_file.name
            st.subheader(f"File: {original_filename}")
            
            default_filename = st.session_state.admin_confirmed_filenames.get(original_filename, original_filename)
            new_filename = st.text_input(
                "Enter filename (must end with .pdf or .docx)",
                value=default_filename,
                key=f"admin_filename_{original_filename}"
            )
            
            if not is_valid_filename(new_filename):
                st.error("Filename must end with .pdf or .docx and contain only alphanumeric characters, underscores, hyphens, or spaces.")
                continue
            
            if os.path.exists(os.path.join(UPLOAD_DIR, new_filename)) and new_filename != original_filename:
                st.error(f"A file named '{new_filename}' already exists.")
                continue

            if st.button("Confirm Upload", key=f"admin_confirm_{original_filename}"):
                st.session_state.admin_confirmed_filenames[original_filename] = new_filename
                confirmed_files.append((uploaded_file, new_filename))
                st.success(f"Filename '{new_filename}' confirmed for upload.")

        if confirmed_files:
            st.write("### Processing Confirmed Files")
            for uploaded_file, filename in confirmed_files:
                file_path = os.path.join(UPLOAD_DIR, filename)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                if filename.lower().endswith('.pdf'):
                    text, tables = extract_content_from_pdf(uploaded_file, filename)
                else:
                    text, tables = extract_content_from_docx(uploaded_file, filename)

                if text:
                    st.write("*Extracted Text:*")
                    st.text_area("Text", text, height=200, key=f"admin_text_{filename}")
                else:
                    st.warning("No text extracted from the document. This might be a scanned PDF or an unsupported format.")

                if tables:
                    st.write("*Extracted Tables:*")
                    st.text_area("Tables", tables, height=200, key=f"admin_tables_{filename}")
                else:
                    st.info("No tables found in the document.")

                # Use the currently logged-in admin's ID instead of hardcoding "admin"
                store_document_content(filename, text, tables, st.session_state.admin_id)

                if uploaded_file.name in st.session_state.admin_confirmed_filenames:
                    del st.session_state.admin_confirmed_filenames[uploaded_file.name]

    if st.button("Back to Dashboard"):
        st.session_state.page = "admin_dashboard"
        st.rerun()

def admin_navigation_bar():
    st.markdown("---")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Admin Dashboard"):
            st.session_state.page = "admin_dashboard"
            st.rerun()
    with col2:
        if st.session_state.admin_id:
            if st.button("Logout"):
                st.session_state.admin_id = None
                st.session_state.logged_in_user = None
                st.session_state.user_details = {}
                st.session_state.page = "login"
                st.rerun()
    st.markdown("---")

def parse_search_query(query):
    params = {
        "username": "",
        "user_id": "",
        "start_date": None,
        "end_date": None,
        "start_time": None,
        "end_time": None,
        "text_query": "",
        "filename": ""
    }
    
    # Step 1: Look for time patterns (HH:MM:SS)
    time_pattern = r'\d{2}:\d{2}:\d{2}'
    times = re.findall(time_pattern, query)
    if times:
        times.sort()
        if len(times) >= 1:
            params["start_time"] = datetime.strptime(times[0], '%H:%M:%S').time()
        if len(times) >= 2:
            params["end_time"] = datetime.strptime(times[-1], '%H:%M:%S').time()
    
    # Remove times from query
    query_clean = re.sub(time_pattern, '', query).strip()
    
    # Step 2: Look for date patterns (YYYY/MM/DD)
    date_pattern = r'\d{4}/\d{2}/\d{2}'
    dates = re.findall(date_pattern, query_clean)
    if dates:
        dates.sort()
        # Convert dates from IST to UTC (subtract 5 hours 30 minutes)
        ist_offset = timedelta(hours=5, minutes=30)
        if len(dates) >= 1:
            ist_date = datetime.strptime(dates[0], '%Y/%m/%d')
            utc_date = ist_date - ist_offset
            params["start_date"] = utc_date.date()
        if len(dates) >= 2:
            ist_date = datetime.strptime(dates[-1], '%Y/%m/%d')
            utc_date = ist_date - ist_offset
            params["end_date"] = utc_date.date()
    
    # Remove dates from query
    query_clean = re.sub(date_pattern, '', query_clean).strip()
    
    # Step 3: Look for filename (require .pdf or .docx extension)
    filename_pattern = r'\b[\w\s\-_]+\.(pdf|docx)\b'
    filenames = re.findall(filename_pattern, query_clean, re.IGNORECASE)
    if filenames:
        params["filename"] = filenames[0].strip()  # Store the exact filename and ensure no extra spaces
        query_clean = re.sub(filename_pattern, '', query_clean, 1).strip()  # Remove only the first match
    
    # Step 4: Look for user_id (only if not already set as part of filename)
    user_id_pattern = r'\b[A-Za-z0-9]{2,10}\b'
    user_ids = re.findall(user_id_pattern, query_clean)
    if user_ids:
        params["user_id"] = user_ids[0]
        query_clean = re.sub(user_id_pattern, '', query_clean).strip()
    
    # Step 5: Look for username (only if not already set)
    words = query_clean.split()
    if words and not params["username"]:
        params["username"] = words[0]
        query_clean = " ".join(words[1:]).strip()
    
    # Step 6: Remaining text is treated as text content keywords
    params["text_query"] = query_clean if query_clean else ""
    
    return params

def admin_dashboard_page():
    st.title("Admin Dashboard")
    st.write("View all uploaded documents and search by username, user ID, upload date, upload time, filename, or text content.")

    if not st.session_state.get("admin_id"):
        st.error("Please log in as admin.")
        st.session_state.page = "admin_login"
        st.rerun()
        return

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Upload Files"):
            st.session_state.page = "admin_upload"
            st.rerun()
    with col2:
        if st.button("Search"):
            st.session_state.show_search = True

    # Fetch documents uploaded by the currently logged-in admin
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        query = """
            SELECT d.filename, d.user_id, d.upload_time, d.extracted_text, d.extracted_tables, l.name
            FROM documents d
            LEFT JOIN log_details l ON d.user_id = l.username
            WHERE d.user_id = %s
        """
        cursor.execute(query, (st.session_state.admin_id,))
        all_documents = cursor.fetchall()
        cursor.close()
        conn.close()
    else:
        st.error("Failed to connect to the database while fetching all documents.")
        all_documents = []

    # Display table of documents using st.dataframe
    st.subheader("All Documents")
    if all_documents:
        table_data = []
        for doc in all_documents:
            filename, user_id, upload_time, text, tables, username = doc
            file_name, file_extension = os.path.splitext(filename)
            table_data.append({
                "File Name": file_name,
                "Extension": file_extension,
                "Uploaded By": user_id,  # Display the user_id directly since it's the admin_id
                "Uploaded At": upload_time,
                "Filename": filename
            })

        df = pd.DataFrame(table_data)
        displayed_df = df[["File Name", "Extension", "Uploaded By", "Uploaded At"]]
        st.dataframe(displayed_df, use_container_width=True)
    else:
        st.info("No documents available.")

    # Search functionality for username, user ID, upload date, upload time, filename, and text content
    if "show_search" not in st.session_state:
        st.session_state.show_search = False

    if st.session_state.show_search:
        st.subheader("Search Documents")
        search_query = st.text_input("Search (e.g., 'Hari 2025/05/13 14:30:00 15:00:00 transport.pdf keywords')", key="dynamic_search")
        
        documents = []
        if search_query:
            params = parse_search_query(search_query)
            
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                query = """
                    SELECT d.filename, d.user_id, d.upload_time, d.extracted_text, d.extracted_tables, l.name
                    FROM documents d
                    LEFT JOIN log_details l ON d.user_id = l.username
                    WHERE d.user_id = %s
                """
                query_params = [st.session_state.admin_id]
                
                if params["username"]:
                    query += " AND (l.name LIKE %s OR d.user_id LIKE %s)"
                    query_params.extend([f"%{params['username']}%", f"%{params['username']}%"])
                if params["user_id"]:
                    query += " AND d.user_id LIKE %s"
                    query_params.append(f"%{params['user_id']}%")
                if params["start_date"]:
                    query += " AND DATE(d.upload_time) >= %s"
                    query_params.append(params["start_date"])
                if params["end_date"]:
                    query += " AND DATE(d.upload_time) <= %s"
                    query_params.append(params["end_date"])
                if params["start_time"]:
                    query += " AND TIME(d.upload_time) >= %s"
                    query_params.append(params["start_time"])
                if params["end_time"]:
                    query += " AND TIME(d.upload_time) <= %s"
                    query_params.append(params["end_time"])
                if params["filename"]:
                    query += " AND LOWER(d.filename) = LOWER(%s)"  # Exact match for filename
                    query_params.append(params["filename"])
                if params["text_query"]:
                    query += " AND d.extracted_text LIKE %s"
                    query_params.append(f"%{params['text_query']}%")
                
                cursor.execute(query, query_params)
                documents = cursor.fetchall()
                cursor.close()
                conn.close()
            else:
                st.error("Failed to connect to the database while searching documents.")

        if documents:
            if "current_page" not in st.session_state:
                st.session_state.current_page = 0
            if "docs_per_page" not in st.session_state:
                st.session_state.docs_per_page = 5

            total_docs = len(documents)
            total_pages = (total_docs + st.session_state.docs_per_page - 1) // st.session_state.docs_per_page
            
            start_idx = st.session_state.current_page * st.session_state.docs_per_page
            end_idx = min(start_idx + st.session_state.docs_per_page, total_docs)
            current_docs = documents[start_idx:end_idx]

            table_data = []
            for doc in current_docs:
                filename, user_id, upload_time, text, tables, username = doc
                table_data.append({
                    "Filename": filename,
                    "Username": username if username else user_id,
                    "User ID": user_id,
                    "Upload Time": upload_time
                })

            st.write(f"**Total Documents Found:** {total_docs}")
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True)

            st.session_state["search_results"] = documents

            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.session_state.current_page > 0:
                    if st.button("Previous"):
                        st.session_state.current_page -= 1
                        st.rerun()
            with col2:
                st.write(f"Page {st.session_state.current_page + 1} of {total_pages}")
            with col3:
                if end_idx < total_docs:
                    if st.button("Next"):
                        st.session_state.current_page += 1
                        st.rerun()

            st.subheader("Document Details")
            selected_filename = st.selectbox("Select a document to view details", [doc[0] for doc in current_docs])
            if selected_filename:
                selected_doc = next(doc for doc in documents if doc[0] == selected_filename)
                filename, user_id, upload_time, text, tables, username = selected_doc
                with st.expander(f"Details for: {filename}", expanded=True):
                    st.write(f"**Filename:** {filename}")
                    st.write(f"**User ID:** {user_id}")
                    st.write(f"**Username:** {username if username else 'N/A'}")
                    st.write(f"**Upload Time:** {upload_time}")
                    if text:
                        st.write("**Extracted Text:**")
                        st.text_area("Text", text, height=200, key=f"admin_text_{filename}_{upload_time}")
                    if tables:
                        st.write("**Extracted Tables:**")
                        st.text_area("Tables", tables, height=200, key=f"admin_tables_{filename}_{upload_time}")
                    
                    file_path = os.path.join(UPLOAD_DIR, filename)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            st.download_button(
                                label="Download File",
                                data=file,
                                file_name=filename,
                                mime="application/pdf" if filename.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"search_results_download_{filename}_{upload_time}"
                            )
                    else:
                        st.warning("The original file is not available for download.")
        else:
            st.info("No documents found matching the search criteria.")

        # Moved "Download a File" section inside the Search section
        st.subheader("Download a File")
        df = pd.DataFrame([{
            "Filename": doc[0]
        } for doc in all_documents])
        if not df.empty:
            selected_filename = st.selectbox("Select a file to download", df["Filename"])
            if selected_filename:
                file_path = os.path.join(UPLOAD_DIR, selected_filename)
                if os.path.exists(file_path):
                    with open(file_path, "rb") as file:
                        st.download_button(
                            label=f"Download {selected_filename}",
                            data=file,
                            file_name=selected_filename,
                            mime="application/pdf" if selected_filename.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"all_docs_download_{selected_filename}"
                        )
                else:
                    st.warning("The selected file is not available for download.")
        else:
            st.info("No documents available to download.")

        # Moved "Search File Content by Specific Word" section inside the Search section
        st.subheader("Search File Content by Specific Word")
        specific_word = st.text_input("Enter a specific word to search in file content", key="specific_word_search")
        
        if specific_word:
            # Normalize the search term
            specific_word = specific_word.strip()
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Use LOWER() to make the search case-insensitive
                query = """
                    SELECT fc.filename, fc.user_id, fc.upload_time, fc.extracted_text, l.name
                    FROM file_content fc
                    LEFT JOIN log_details l ON fc.user_id = l.username
                    WHERE LOWER(fc.extracted_text) LIKE LOWER(%s)
                    AND fc.user_id = %s
                """
                search_pattern = f"%{specific_word}%"
                cursor.execute(query, (search_pattern, st.session_state.admin_id))
                matching_docs = cursor.fetchall()
                
                if matching_docs:
                    st.write(f"**Total Documents Found:** {len(matching_docs)}")
                    for doc in matching_docs:
                        filename, user_id, upload_time, text, username = doc
                        st.subheader(f"File: {filename}")
                        st.write(f"**Filename:** {filename}")
                        st.write(f"**User ID:** {user_id}")
                        st.write(f"**Username:** {username if username else 'N/A'}")
                        st.write(f"**Upload Time:** {upload_time}")
                        if text:
                            st.write("**Extracted Text (with search term highlighted):**")
                            # Highlight the search term in the extracted text
                            highlighted_text = re.sub(
                                f"({re.escape(specific_word)})",
                                r"**\1**",
                                text,
                                flags=re.IGNORECASE
                            )
                            st.text_area("Text", highlighted_text, height=200, key=f"content_search_text_{filename}_{upload_time}")
                        
                        file_path = os.path.join(UPLOAD_DIR, filename)
                        if os.path.exists(file_path):
                            with open(file_path, "rb") as file:
                                st.download_button(
                                    label="Download File",
                                    data=file,
                                    file_name=filename,
                                    mime="application/pdf" if filename.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"content_search_download_{filename}_{upload_time}"
                                )
                        else:
                            st.warning("The original file is not available for download.")
                else:
                    st.info("No documents found containing the specified word.")
                
                cursor.close()
                conn.close()
            else:
                st.error("Failed to connect to the database while searching for specific word.")

        # Add "Back to Home" button to return to the Admin Dashboard homepage
        if st.button("Back to Home"):
            st.session_state.show_search = False
            st.session_state.page = "admin_dashboard"
            st.rerun()

def login_page():
    st.title("Document Reader App")
    st.write("Log in or sign up to upload and manage documents.")

    st.markdown("### Login Options")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Admin Login")
        if st.button("Admin Sign In"):
            st.session_state.page = "admin_login"
            st.rerun()
    with col2:
        st.subheader("New Admin")
        if st.button("Admin Sign Up"):
            st.session_state.page = "admin_sign_up"
            st.rerun()

def admin_sign_up_page():
    st.title("Admin Sign Up")
    admin_id = st.text_input("Admin ID")
    password = st.text_input("Password", type="password")

    if st.button("Register"):
        if register_admin(admin_id, password):
            st.session_state.page = "login"
            st.rerun()

    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.rerun()

def admin_login_page():
    st.title("Admin Login")
    admin_id = st.text_input("Admin ID")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if authenticate_admin(admin_id, password):
            st.session_state.page = "admin_dashboard"
            st.rerun()
        else:
            st.error("Invalid admin credentials.")

    if st.button("Back to Login"):
        st.session_state.page = "login"
        st.rerun()

def main():
    create_log_details_table()
    create_documents_table()
    create_file_content_table()
    create_admins_table()

    if "page" not in st.session_state:
        st.session_state.page = "login"
    if "logged_in_user" not in st.session_state:
        st.session_state.logged_in_user = None
    if "user_details" not in st.session_state:
        st.session_state.user_details = {}
    if "admin_id" not in st.session_state:
        st.session_state.admin_id = None
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "admin_confirmed_filenames" not in st.session_state:
        st.session_state.admin_confirmed_filenames = {}

    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "admin_sign_up":
        admin_sign_up_page()
    elif st.session_state.page == "admin_login":
        admin_login_page()
    elif st.session_state.page == "admin_dashboard":
        admin_navigation_bar()
        admin_dashboard_page()
    elif st.session_state.page == "admin_upload":
        admin_navigation_bar()
        admin_upload_page()

if __name__ == "__main__":
    main()