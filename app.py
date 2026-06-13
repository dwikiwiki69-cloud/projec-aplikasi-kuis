from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sikc_poltekba_key' # Kunci pengaman untuk session

# ================= 1. FUNGSI KONEKSI DATABASE (SQLITE) =================
def get_db_connection():
    # Menggunakan SQLite berbasis file 'database.db' (Gratis di PythonAnywhere)
    conn = sqlite3.connect('database.db')
    # Mengubah hasil query menjadi format dictionary agar kompatibel dengan kode lama Anda
    conn.row_factory = sqlite3.Row
    return conn

# ================= 2. OTOMATISASI PEMBUATAN TABEL SAAT APLIKASI JALAN =================
def inisialisasi_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabel Pengguna (Mahasiswa) - Menggunakan AUTOINCREMENT khas SQLite
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nim TEXT UNIQUE,
        nama TEXT
    )
    ''')
    
    # Tabel Kuis
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        judul TEXT,
        deadline TEXT
    )
    ''')
    
    # Tabel Soal
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER,
        pertanyaan TEXT,
        opsi_a TEXT,
        opsi_b TEXT,
        opsi_c TEXT,
        opsi_d TEXT,
        jawaban_benar TEXT
    )
    ''')
    
    # Tabel Nilai & Komentar
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        quiz_id INTEGER,
        nilai_total INTEGER,
        komentar TEXT,
        waktu_submit TEXT
    )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

# Jalankan fungsi pembuatan tabel di atas secara aman
try:
    inisialisasi_database()
except Exception as e:
    print(f"Log info: {e}")


# ================= 3. KORIDOR MAHASISWA =================

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nama = request.form['nama']
        nim = request.form['nim']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Mengubah %s menjadi ? khas SQLite
            cursor.execute('INSERT INTO users (nim, nama) VALUES (?, ?)', (nim, nama))
            conn.commit()
        except sqlite3.IntegrityError:
            # Menangani NIM yang sudah terdaftar secara aman di SQLite
            pass
            
        cursor.execute('SELECT * FROM users WHERE nim = ?', (nim,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['nama'] = user['nama']
            session['nim'] = user['nim']
            session['role'] = 'user'
            return redirect(url_for('dashboard_kuis'))
        
    return render_template('login.html')

@app.route('/dashboard')
def dashboard_kuis():
    if 'user_id' not in session: return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM quizzes')
    quizzes = cursor.fetchall()
    
    cursor.execute('SELECT quiz_id, nilai_total, komentar FROM grades WHERE user_id = ?', (session['user_id'],))
    grades = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    status_kuis = {g['quiz_id']: {'nilai': g['nilai_total'], 'komentar': g['komentar']} for g in grades}
    waktu_sekarang = datetime.now()
    
    return render_template('kuis.html', quizzes=quizzes, status_kuis=status_kuis, waktu_sekarang=waktu_sekarang)

@app.route('/kerjakan/<int:quiz_id>', methods=['GET', 'POST'])
def kerjakan_kuis(quiz_id):
    if 'user_id' not in session: return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,))
    kuis = cursor.fetchone()
    
    waktu_sekarang = datetime.now()
    
    # SQLite menyimpan datetime sebagai string text, kita parse kembali ke objek datetime Python
    if kuis and kuis['deadline']:
        try:
            deadline_dt = datetime.strptime(kuis['deadline'], '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                deadline_dt = datetime.strptime(kuis['deadline'], '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                deadline_dt = datetime.strptime(kuis['deadline'], '%Y-%m-%d %H:%M:%S')
                
        if waktu_sekarang > deadline_dt:
            cursor.close()
            conn.close()
            flash("Maaf, batas waktu (deadline) kuis ini sudah habis!")
            return redirect(url_for('dashboard_kuis'))

    if request.method == 'POST':
        cursor.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,))
        questions = cursor.fetchall()
        
        jawaban_benar_count = 0
        total_soal = len(questions)

        for q in questions:
            jawaban_user = request.form.get(f"question_{q['id']}")
            if jawaban_user == q['jawaban_benar']:
                jawaban_benar_count += 1
        
        nilai_akhir = int((jawaban_benar_count / total_soal) * 100) if total_soal > 0 else 0

        cursor.execute('''
            INSERT INTO grades (user_id, quiz_id, nilai_total, komentar, waktu_submit)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], quiz_id, nilai_akhir, '', waktu_sekarang))
        
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard_kuis'))

    cursor.execute('SELECT * FROM questions WHERE quiz_id = ?', (quiz_id,))
    questions = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('soal.html', kuis=kuis, questions=questions)


# ================= 4. KORIDOR ADMIN (PENGAJAR) =================

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT users.nama, users.nim, quizzes.judul, grades.nilai_total, grades.komentar, grades.id as grade_id
            FROM grades
            JOIN users ON grades.user_id = users.id
            JOIN quizzes ON grades.quiz_id = quizzes.id
        ''')
        peserta_nilai = cursor.fetchall()
        
        cursor.execute('SELECT * FROM quizzes')
        quizzes = cursor.fetchall()
        
        cursor.execute('''
            SELECT questions.id, questions.pertanyaan, quizzes.judul 
            FROM questions 
            JOIN quizzes ON questions.quiz_id = quizzes.id
        ''')
        all_questions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return render_template('admin.html', peserta_nilai=peserta_nilai, quizzes=quizzes, all_questions=all_questions)
        
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin123':
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
            
    return render_template('admin_login.html')

@app.route('/admin/tambah-kuis', methods=['POST'])
def tambah_kuis():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    judul = request.form['judul']
    deadline = request.form['deadline']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO quizzes (judul, deadline) VALUES (?, ?)', (judul, deadline))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/hapus-kuis/<int:quiz_id>')
def hapus_kuis(quiz_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
    cursor.execute('DELETE FROM questions WHERE quiz_id = ?', (quiz_id,))
    cursor.execute('DELETE FROM grades WHERE quiz_id = ?', (quiz_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/tambah-soal', methods=['POST'])
def tambah_soal():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    quiz_id = request.form['quiz_id']
    pertanyaan = request.form['pertanyaan']
    opsi_a = request.form['opsi_a']
    opsi_b = request.form['opsi_b']
    opsi_c = request.form['opsi_c']
    opsi_d = request.form['opsi_d']
    jawaban_benar = request.form['jawaban_benar']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO questions (quiz_id, pertanyaan, opsi_a, opsi_b, opsi_c, opsi_d, jawaban_benar)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (quiz_id, pertanyaan, opsi_a, opsi_b, opsi_c, opsi_d, jawaban_benar))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/hapus-soal/<int:question_id>')
def hapus_soal(question_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM questions WHERE id = ?', (question_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/komentar/<int:grade_id>', methods=['GET', 'POST'])
def beri_komentar(grade_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        komentar = request.form['komentar']
        cursor.execute('UPDATE grades SET komentar = ? WHERE id = ?', (komentar, grade_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))
        
    cursor.execute('''
        SELECT grades.*, users.nama, users.nim 
        FROM grades 
        JOIN users ON grades.user_id = users.id 
        WHERE grades.id = ?
    ''', (grade_id,))
    data = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('komentar.html', data=data)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)