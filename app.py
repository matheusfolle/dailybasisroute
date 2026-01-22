from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, date
import pytz
import json
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dailybasisroute-secret-key-2025')

# Configuração do banco de dados
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:31528899japan@db.flzqqwelasfzipzahzqw.supabase.co:5432/postgres')

# Timezone brasileiro
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

def get_brazil_now():
    """Retorna datetime atual no timezone do Brasil"""
    return datetime.now(BRAZIL_TZ)

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Inicializa o banco de dados com as tabelas necessárias"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Tabela de usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de tarefas (definições)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT,
            points REAL NOT NULL,
            details TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabela de registros diários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            task_id INTEGER NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (task_id) REFERENCES tasks (id),
            UNIQUE(user_id, date, task_id)
        )
    ''')
    
    # Tabela de notas diárias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            content TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')
    
    # Tabela de streaks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS streaks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL,
            current_streak INTEGER DEFAULT 0,
            last_completion_date DATE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabela de tarefas customizadas do dia
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            name TEXT NOT NULL,
            points INTEGER NOT NULL,
            completed BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabela de humor diário
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_mood (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            mood_score INTEGER NOT NULL CHECK (mood_score >= 0 AND mood_score <= 100),
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')
    
    # Tabela de relatórios diários (4 perguntas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_reports (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            work_performance INTEGER CHECK (work_performance >= 1 AND work_performance <= 10),
            accomplishment TEXT,
            challenge TEXT,
            random_thought TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')
    
    # Tabela de desempenho no trabalho (para heatmap)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_performance (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date DATE NOT NULL,
            performance_score INTEGER NOT NULL CHECK (performance_score >= 1 AND performance_score <= 10),
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()

def setup_default_tasks(user_id):
    """Create default tasks for a new user"""
    conn = get_db()
    cursor = conn.cursor()  # Normal cursor
    
    default_tasks = {
        'pillars': [
            {'name': 'Daily Devotion', 'emoji': 'prayer', 'points': 15, 'details': 'Morning OR evening - 25min'},
            {'name': 'Slept Before 11PM', 'emoji': 'bed', 'points': 10, 'details': 'Sleep routine'},
            {'name': 'Woke Up Early', 'emoji': 'sunrise', 'points': 10, 'details': 'Got up without snoozing!'},
            {'name': 'Completed Google Agenda Tasks', 'emoji': 'calendar-check', 'points': 15, 'details': 'All tasks from previous day'},
        ],
        'tasks': [
            {'name': 'Programming', 'emoji': 'code', 'points': 15, 'details': '1-2h focused study'},
            {'name': 'English', 'emoji': 'language', 'points': 10, 'details': '30min-1h practice'},
            {'name': 'SQL', 'emoji': 'database', 'points': 10, 'details': '30min-1h hands-on'},
            {'name': 'Physical Activity', 'emoji': 'dumbbell', 'points': 15, 'details': 'Gym, bike ride, running'},
            {'name': 'Reading', 'emoji': 'book-open', 'points': 10, 'details': 'Technical books, articles'},
        ],
        'bonus': [
            {'name': 'Obsidian Thoughts', 'emoji': 'brain', 'points': 5, 'details': 'Knowledge management'},
            {'name': 'Bike Ride', 'emoji': 'bicycle', 'points': 10, 'details': 'Cycling session'},
            {'name': 'Focused Training <90min', 'emoji': 'stopwatch', 'points': 5, 'details': 'Efficient gym session'},
            {'name': 'Deep Work Block >2hrs', 'emoji': 'crosshairs', 'points': 10, 'details': 'Uninterrupted focus'},
            {'name': 'Global Student', 'emoji': 'globe', 'points': 5, 'details': 'Studied skills for global collaboration'},
        ]
    }
    
    for category, tasks_list in default_tasks.items():
        for task in tasks_list:
            cursor.execute('''
                INSERT INTO tasks (user_id, category, name, emoji, points, details)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (user_id, category, task['name'], task['emoji'], task['points'], task['details']))
    
    # Create streak record
    cursor.execute('INSERT INTO streaks (user_id) VALUES (%s)', (user_id,))
    
    conn.commit()
    conn.close()

# Rotas
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        return redirect(url_for('dashboard'))
    
    return redirect(url_for('index', error='invalid'))

@app.route('/cadastro', methods=['POST'])
def cadastro():
    email = request.form.get('email')
    password = request.form.get('password')
    name = request.form.get('name')
    
    conn = get_db()
    cursor = conn.cursor()  # Cursor normal, não RealDictCursor
    
    try:
        cursor.execute('''
            INSERT INTO users (email, password_hash, name)
            VALUES (%s, %s, %s) RETURNING id
        ''', (email, generate_password_hash(password), name))
        user_id = cursor.fetchone()[0]
        conn.commit()
        
        # Setup tarefas padrão
        setup_default_tasks(user_id)
        
        session['user_id'] = user_id
        session['user_name'] = name
        conn.close()
        return redirect(url_for('dashboard'))
    except psycopg2.IntegrityError:
        conn.close()
        return redirect(url_for('index', error='exists'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    today = get_brazil_now().date().isoformat()
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Buscar tarefas do usuário
    cursor.execute('''
        SELECT t.*, 
               COALESCE(dl.completed, FALSE) as completed
        FROM tasks t
        LEFT JOIN daily_logs dl ON t.id = dl.task_id 
            AND dl.user_id = %s AND dl.date = %s
        WHERE t.user_id = %s
        ORDER BY t.category, t.id
    ''', (user_id, today, user_id))
    tasks = cursor.fetchall()
    
    # Buscar tarefas customizadas do dia
    cursor.execute('''
        SELECT * FROM custom_tasks 
        WHERE user_id = %s AND date = %s
        ORDER BY id
    ''', (user_id, today))
    custom_tasks = cursor.fetchall()
    
    # Buscar nota do dia
    cursor.execute('''
        SELECT content FROM notes WHERE user_id = %s AND date = %s
    ''', (user_id, today))
    note = cursor.fetchone()
    
    # Buscar streak
    cursor.execute('''
        SELECT current_streak FROM streaks WHERE user_id = %s
    ''', (user_id,))
    streak_data = cursor.fetchone()
    
    # Buscar mood do dia
    cursor.execute('''
        SELECT mood_score FROM daily_mood WHERE user_id = %s AND date = %s
    ''', (user_id, today))
    mood_data = cursor.fetchone()
    
    conn.close()
    
    # Organize tasks by category
    tasks_by_category = {'pillars': [], 'tasks': [], 'bonus': []}
    for task in tasks:
        tasks_by_category[task['category']].append(dict(task))
    
    return render_template('dashboard.html',
                         tasks=tasks_by_category,
                         custom_tasks=[dict(ct) for ct in custom_tasks],
                         note=note['content'] if note else '',
                         streak=streak_data['current_streak'] if streak_data else 0,
                         mood=mood_data['mood_score'] if mood_data else 50,
                         today=today)

@app.route('/api/toggle_task', methods=['POST'])
def toggle_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    task_id = request.json.get('task_id')
    date = request.json.get('date', get_brazil_now().date().isoformat())
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if record exists
    cursor.execute('''
        SELECT completed FROM daily_logs 
        WHERE user_id = %s AND task_id = %s AND date = %s
    ''', (user_id, task_id, date))
    existing = cursor.fetchone()
    
    if existing:
        new_status = not existing['completed']
        cursor.execute('''
            UPDATE daily_logs SET completed = %s 
            WHERE user_id = %s AND task_id = %s AND date = %s
        ''', (new_status, user_id, task_id, date))
    else:
        cursor.execute('''
            INSERT INTO daily_logs (user_id, task_id, date, completed)
            VALUES (%s, %s, %s, TRUE)
        ''', (user_id, task_id, date))
    
    # OPTIMIZED: Single query for total points
    cursor.execute('''
        SELECT 
            (SELECT COALESCE(SUM(t.points), 0)
             FROM daily_logs dl
             JOIN tasks t ON dl.task_id = t.id
             WHERE dl.user_id = %s AND dl.date = %s AND dl.completed = TRUE) +
            (SELECT COALESCE(SUM(points), 0)
             FROM custom_tasks
             WHERE user_id = %s AND date = %s) as total_points,
            (SELECT current_streak FROM streaks WHERE user_id = %s) as current_streak,
            (SELECT last_completion_date FROM streaks WHERE user_id = %s) as last_date
    ''', (user_id, date, user_id, date, user_id, user_id))
    
    result = cursor.fetchone()
    total_points = float(result['total_points'])
    current_streak = result['current_streak'] or 0
    last_date = result['last_date']
    
    # Update streak if >= 70 points
    # Update streak if >= 70 points
    if total_points >= 60:  # Also fixed your threshold - you had 60 here
        if last_date:
        # Database already returns date object, just use it
            current_date_obj = datetime.fromisoformat(date).date()
            diff = (current_date_obj - last_date).days
        
        if diff == 1:
            current_streak += 1
        elif diff > 1:
            current_streak = 1
    else:
        current_streak = 1
        
        cursor.execute('''
            UPDATE streaks 
            SET current_streak = %s, last_completion_date = %s
            WHERE user_id = %s
        ''', (current_streak, date, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'total_points': total_points,
        'streak': current_streak
    })

@app.route('/api/save_note', methods=['POST'])
def save_note():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    content = request.json.get('content')
    date = request.json.get('date', get_brazil_now().date().isoformat())
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO notes (user_id, date, content)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET content = EXCLUDED.content
    ''', (user_id, date, content))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/save_mood', methods=['POST'])
def save_mood():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    mood_score = request.json.get('mood_score')
    date = request.json.get('date', get_brazil_now().date().isoformat())
    
    # Validar mood_score
    if mood_score is None or mood_score < 0 or mood_score > 100:
        return jsonify({'error': 'Invalid mood score'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO daily_mood (user_id, date, mood_score)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET mood_score = EXCLUDED.mood_score
    ''', (user_id, date, mood_score))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/save_daily_report', methods=['POST'])
def save_daily_report():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    data = request.json
    date = data.get('date', get_brazil_now().date().isoformat())
    
    work_performance = data.get('work_performance')
    accomplishment = data.get('accomplishment', '')
    challenge = data.get('challenge', '')
    random_thought = data.get('random_thought', '')
    
    # Validate work_performance
    if work_performance is not None:
        if work_performance < 1 or work_performance > 10:
            return jsonify({'error': 'Invalid work performance score'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO daily_reports (user_id, date, work_performance, accomplishment, challenge, random_thought)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, date) 
        DO UPDATE SET 
            work_performance = EXCLUDED.work_performance,
            accomplishment = EXCLUDED.accomplishment,
            challenge = EXCLUDED.challenge,
            random_thought = EXCLUDED.random_thought
    ''', (user_id, date, work_performance, accomplishment, challenge, random_thought))
    
    # Also save work_performance to work_performance table for heatmap
    if work_performance is not None:
        cursor.execute('''
            INSERT INTO work_performance (user_id, date, performance_score)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, date)
            DO UPDATE SET performance_score = EXCLUDED.performance_score
        ''', (user_id, date, work_performance))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/add_custom_task', methods=['POST'])
def add_custom_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    name = request.json.get('name')
    points = request.json.get('points')
    date = request.json.get('date', get_brazil_now().date().isoformat())
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO custom_tasks (user_id, date, name, points, completed)
        VALUES (%s, %s, %s, %s, TRUE) RETURNING id
    ''', (user_id, date, name, points))
    
    task_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/api/delete_custom_task', methods=['POST'])
def delete_custom_task():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    task_id = request.json.get('task_id')
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute('''
        DELETE FROM custom_tasks 
        WHERE id = %s AND user_id = %s
    ''', (task_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/stats')
def get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Últimos 7 dias - tarefas normais
    cursor.execute('''
        SELECT dl.date, SUM(t.points) as points
        FROM daily_logs dl
        JOIN tasks t ON dl.task_id = t.id
        WHERE dl.user_id = %s AND dl.completed = TRUE
            AND dl.date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY dl.date
        ORDER BY dl.date
    ''', (user_id,))
    week_data_tasks = cursor.fetchall()
    
    # Últimos 7 dias - tarefas customizadas
    cursor.execute('''
        SELECT date, SUM(points) as points
        FROM custom_tasks
        WHERE user_id = %s AND date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY date
        ORDER BY date
    ''', (user_id,))
    week_data_custom = cursor.fetchall()
    
    # Últimos 30 dias - tarefas normais
    cursor.execute('''
        SELECT dl.date, SUM(t.points) as points
        FROM daily_logs dl
        JOIN tasks t ON dl.task_id = t.id
        WHERE dl.user_id = %s AND dl.completed = TRUE
            AND dl.date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY dl.date
        ORDER BY dl.date
    ''', (user_id,))
    month_data_tasks = cursor.fetchall()
    
    # Últimos 30 dias - tarefas customizadas
    cursor.execute('''
        SELECT date, SUM(points) as points
        FROM custom_tasks
        WHERE user_id = %s AND date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY date
        ORDER BY date
    ''', (user_id,))
    month_data_custom = cursor.fetchall()
    
    # Mood dos últimos 30 dias
    cursor.execute('''
        SELECT date, mood_score
        FROM daily_mood
        WHERE user_id = %s AND date >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY date
    ''', (user_id,))
    mood_data = cursor.fetchall()
    
    conn.close()
    
    # Combinar pontos por data
    def combine_points(tasks_data, custom_data):
        combined = {}
        for row in tasks_data:
            date = str(row['date'])
            combined[date] = float(row['points']) if row['points'] else 0
        for row in custom_data:
            date = str(row['date'])
            combined[date] = combined.get(date, 0) + (float(row['points']) if row['points'] else 0)
        return [{'date': date, 'points': points} for date, points in sorted(combined.items())]
    
    week_combined = combine_points(week_data_tasks, week_data_custom)
    month_combined = combine_points(month_data_tasks, month_data_custom)
    
    return jsonify({
        'week': week_combined,
        'month': month_combined,
        'mood': [{'date': str(row['date']), 'mood': int(row['mood_score'])} for row in mood_data]
    })

@app.route('/api/export')
def export_data():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    period = request.args.get('period', 'all')  # all, week, biweekly, month
    
    # Definir intervalo de datas
    if period == 'week':
        date_filter = "AND dl.date >= CURRENT_DATE - INTERVAL '7 days'"
    elif period == 'biweekly':
        date_filter = "AND dl.date >= CURRENT_DATE - INTERVAL '14 days'"
    elif period == 'month':
        date_filter = "AND dl.date >= CURRENT_DATE - INTERVAL '30 days'"
    else:
        date_filter = ""
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Buscar dados com filtro de período
    cursor.execute(f'''
    SELECT dl.date, t.name, t.category, t.points, dl.completed, 
           dr.work_performance, dr.accomplishment, dr.challenge, dr.random_thought,
           m.mood_score
    FROM daily_logs dl
    JOIN tasks t ON dl.task_id = t.id
    LEFT JOIN daily_reports dr ON dl.user_id = dr.user_id AND dl.date = dr.date
    LEFT JOIN daily_mood m ON dl.user_id = m.user_id AND dl.date = m.date
    WHERE dl.user_id = %s {date_filter}
    ORDER BY dl.date DESC
''', (user_id,))
    logs = cursor.fetchall()
    
    # Buscar tarefas customizadas
    cursor.execute(f'''
        SELECT date, name, points
        FROM custom_tasks
        WHERE user_id = %s {date_filter.replace('dl.date', 'date')}
        ORDER BY date DESC
    ''', (user_id,))
    custom_logs = cursor.fetchall()
    
    conn.close()
    
    # Organizar dados por dia
    data_by_date = {}
    for log in logs:
        date = str(log['date'])
        if date not in data_by_date:
            data_by_date[date] = {
                'date': date,
                'tasks': [],
                'total_points': 0,
                'work_performance': int(log['work_performance']) if log['work_performance'] is not None else None,
                'accomplishment': log['accomplishment'],
                'challenge': log['challenge'],
                'random_thought': log['random_thought'],
                'mood': int(log['mood_score']) if log['mood_score'] is not None else None
            }
        
        if log['completed']:
            data_by_date[date]['tasks'].append({
                'name': log['name'],
                'category': log['category'],
                'points': float(log['points'])
            })
            data_by_date[date]['total_points'] += float(log['points'])
    
    # Adicionar tarefas customizadas
    for custom in custom_logs:
        date = str(custom['date'])
        if date not in data_by_date:
            data_by_date[date] = {
                'date': date,
                'tasks': [],
                'total_points': 0,
                'note': None,
                'mood': None
            }
        
        data_by_date[date]['tasks'].append({
            'name': custom['name'],
            'category': 'custom',
            'points': float(custom['points'])
        })
        data_by_date[date]['total_points'] += float(custom['points'])
    
    return jsonify({
        'period': period,
        'data': list(data_by_date.values())
    })

@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('analytics.html')

@app.route('/historico')
def historico():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Últimos 30 dias com pontos das tarefas normais
    cursor.execute('''
        SELECT 
            dl.date,
            SUM(t.points) as total_points,
            COUNT(DISTINCT CASE WHEN dl.completed = TRUE THEN t.id END) as completed_tasks,
            n.content as note
        FROM daily_logs dl
        JOIN tasks t ON dl.task_id = t.id
        LEFT JOIN notes n ON dl.user_id = n.user_id AND dl.date = n.date
        WHERE dl.user_id = %s AND dl.date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY dl.date, n.content
        ORDER BY dl.date DESC
    ''', (user_id,))
    history_tasks = cursor.fetchall()
    
    # Pontos das tarefas customizadas
    cursor.execute('''
        SELECT date, SUM(points) as total_points
        FROM custom_tasks
        WHERE user_id = %s AND date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY date
    ''', (user_id,))
    history_custom = cursor.fetchall()
    
    conn.close()
    
    # Combinar pontos
    history_dict = {}
    for row in history_tasks:
        date = str(row['date'])
        history_dict[date] = {
            'date': date,
            'total_points': float(row['total_points']) if row['total_points'] else 0,
            'completed_tasks': row['completed_tasks'],
            'note': row['note']
        }
    
    for row in history_custom:
        date = str(row['date'])
        if date in history_dict:
            history_dict[date]['total_points'] += float(row['total_points']) if row['total_points'] else 0
        else:
            history_dict[date] = {
                'date': date,
                'total_points': float(row['total_points']) if row['total_points'] else 0,
                'completed_tasks': 0,
                'note': None
            }
    
    # Ordenar por data DESC
    history = sorted(history_dict.values(), key=lambda x: x['date'], reverse=True)
    
    return render_template('historico.html', history=history)

def update_streak(user_id, current_date, points):
    """Atualiza a sequência do usuário"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    streak = cursor.execute('SELECT * FROM streaks WHERE user_id = %s', (user_id,))

    streak = cursor.fetchone()
    
    if not streak:
        cursor.execute('INSERT INTO streaks (user_id) VALUES (%s)', (user_id,))
        conn.commit()
        conn.close()
        return
    
    current_streak = streak['current_streak']
    last_date = streak['last_completion_date']
    
    if points >= 70:
        if last_date:
            last_date_obj = last_date if isinstance(last_date, date) else datetime.fromisoformat(str(last_date)).date()
            current_date_obj = datetime.fromisoformat(current_date).date()
            diff = (current_date_obj - last_date_obj).days
            
            if diff == 1:
                # Dia consecutivo
                current_streak += 1
            elif diff == 0:
                # Mesmo dia, não faz nada
                pass
            else:
                # Quebrou a sequência
                current_streak = 1
        else:
            current_streak = 1
        
        cursor.execute('''
            UPDATE streaks 
            SET current_streak = %s, last_completion_date = %s
            WHERE user_id = %s
        ''', (current_streak, current_date, user_id))
    
    conn.commit()
    conn.close()

@app.route('/api/weekly_progress')
def weekly_progress():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    today = get_brazil_now().date()
    week_ago = today - timedelta(days=7)
    
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get points from regular tasks for the last 7 days
    cursor.execute('''
        SELECT dl.date, SUM(t.points) as points
        FROM daily_logs dl
        JOIN tasks t ON dl.task_id = t.id
        WHERE dl.user_id = %s AND dl.completed = TRUE 
        AND dl.date >= %s AND dl.date <= %s
        GROUP BY dl.date
    ''', (user_id, week_ago, today))
    
    week_tasks = cursor.fetchall()
    
    # Get points from custom tasks for the last 7 days
    cursor.execute('''
        SELECT date, SUM(points) as points
        FROM custom_tasks
        WHERE user_id = %s AND date >= %s AND date <= %s
        GROUP BY date
    ''', (user_id, week_ago, today))
    
    week_custom = cursor.fetchall()
    
    conn.close()
    
    # Combine points by date
    daily_totals = {}
    for row in week_tasks:
        daily_totals[str(row['date'])] = float(row['points']) if row['points'] else 0
    
    for row in week_custom:
        date = str(row['date'])
        daily_totals[date] = daily_totals.get(date, 0) + (float(row['points']) if row['points'] else 0)
    
    # Calculate average (only count days with data)
    if daily_totals:
        avg_points = sum(daily_totals.values()) / len(daily_totals)
        # Assuming max possible is 120 (your "normal day")
        avg_percentage = (avg_points / 120) * 100
    else:
        avg_percentage = 0
    
    return jsonify({'percentage': round(avg_percentage, 1)})


if __name__ == '__main__':
    # Inicializar banco se necessário
    try:
        init_db()
    except Exception as e:
        print(f"Banco já inicializado ou erro: {e}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
