# pip install flask
import json
import threading
import uuid
from uuid import uuid4

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, make_response, \
    jsonify
from LMS.common.session import Session
from LMS.domain.Board import Board
from LMS.domain.Score import Score
from LMS.domain.item import Item
from LMS.service import *

import os


app = Flask(__name__)

#UPLOAD_FOLDER = '/app/uploads'
UPLOAD_FOLDER = 'uploads/'
# 폴더가 없으면 자동 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# 최대 업로드 용량 제한 (예: 16MB)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 1. 게시판 목록 조회
@app.route('/board')
def board_list():
    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 작성자 이름을 함께 가져오기 위해 JOIN 사용
            sql = """
                SELECT b.*, m.name as writer_name 
                FROM boards b 
                JOIN members m ON b.member_id = m.id 
                ORDER BY b.id DESC
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            boards = [Board.from_db(row) for row in rows]
            return render_template('board_list.html', boards=boards)
    finally:
        conn.close()

# 2. 게시글 상세 보기
@app.route('/board/view/<int:board_id>')
def board_view(board_id):
    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # JOIN을 통해 작성자 정보(name, uid)를 함께 조회
            sql = """
                SELECT b.*, m.name as writer_name, m.uid as writer_uid
                FROM boards b
                JOIN members m ON b.member_id = m.id
                WHERE b.id = %s
            """
            cursor.execute(sql, (board_id,))
            row = cursor.fetchone()

            if not row:
                return "<script>alert('존재하지 않는 게시글입니다.'); history.back();</script>"

            # Board 객체로 변환 (앞서 작성한 Board.py의 from_db 활용)
            board = Board.from_db(row)

            return render_template('board_view.html', board=board)
    finally:
        conn.close()

@app.route('/board/write', methods=['GET', 'POST'])
def board_write():
    # 1. 사용자가 '글쓰기' 버튼을 눌러서 들어왔을 때 (화면 보여주기)
    if request.method == 'GET':
        # 로그인 체크 (로그인 안 했으면 글 못 쓰게)
        if 'user_id' not in session:
            return '<script>alert("로그인 후 이용 가능합니다."); location.href="/login";</script>'
        return render_template('board_write.html')

    # 2. 사용자가 '등록하기' 버튼을 눌러서 데이터를 보냈을 때 (DB 저장)
    elif request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        # 세션에 저장된 로그인 유저의 id (member_id)
        member_id = session.get('user_id')

        conn = Session.get_connection()
        try:
            with conn.cursor() as cursor:
                # 기억하신 테이블 구조(member_id, title, content)에 맞게 INSERT
                sql = "INSERT INTO boards (member_id, title, content) VALUES (%s, %s, %s)"
                cursor.execute(sql, (member_id, title, content))
                conn.commit()
            return redirect(url_for('board_list')) # 저장 후 목록으로 이동
        except Exception as e:
            print(f"글쓰기 에러: {e}")
            return "저장 중 에러가 발생했습니다."
        finally:
            conn.close()


@app.route('/board/edit/<int:board_id>', methods=['GET', 'POST'])
def board_edit(board_id):
    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 화면 보여주기 (기존 데이터 로드)
            if request.method == 'GET':
                sql = "SELECT * FROM boards WHERE id = %s"
                cursor.execute(sql, (board_id,))
                row = cursor.fetchone()

                if not row:
                    return "<script>alert('존재하지 않는 게시글입니다.'); history.back();</script>"

                # 본인 확인 로직 (필요시 추가)
                if row['member_id'] != session.get('user_id'):
                    return "<script>alert('수정 권한이 없습니다.'); history.back();</script>"

                board = Board.from_db(row)
                return render_template('board_edit.html', board=board)

            # 2. 실제 DB 업데이트 처리
            elif request.method == 'POST':
                title = request.form.get('title')
                content = request.form.get('content')

                sql = "UPDATE boards SET title=%s, content=%s WHERE id=%s"
                cursor.execute(sql, (title, content, board_id))
                conn.commit()

                return redirect(url_for('board_view', board_id=board_id))
    finally:
        conn.close()


@app.route('/board/delete/<int:board_id>')
def board_delete(board_id):
    # 로그인 여부 확인 (필요시)
    # if 'user_id' not in session:
    #     return '<script>alert("로그인 후 이용 가능합니다."); location.href="/login";</script>'

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 본인 확인 로직을 추가하고 싶다면 WHERE member_id = %s 를 추가하세요.
            sql = "DELETE FROM boards WHERE id = %s"  # 저장된 테이블명 boards 사용
            cursor.execute(sql, (board_id,))
            conn.commit()

            if cursor.rowcount > 0:
                print(f"게시글 {board_id}번 삭제 성공")
            else:
                return "<script>alert('삭제할 게시글이 없거나 권한이 없습니다.'); history.back();</script>"

        return redirect(url_for('board_list'))
    except Exception as e:
        print(f"삭제 에러: {e}")
        return "삭제 중 오류가 발생했습니다."
    finally:
        conn.close()


# 세션을 사용하기 위해 보안키 설정 (아무 문자열이나 입력)
app.secret_key = 'your_secret_key_here'


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    uid = request.form.get('uid')
    upw = request.form.get('upw')

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 회원 정보 조회
            sql = "SELECT id, name, uid, role  FROM members WHERE uid = %s AND password = %s"
            cursor.execute(sql, (uid, upw))
            user = cursor.fetchone()

            if user:
                # 2. 로그인 성공: 세션에 사용자 정보 저장
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_uid'] = user['uid']

                # 이제 DB에서 'role'을 가져왔으니 에러 없이 잘 들어갈 겁니다.
                session['user_role'] = user['role']

                return redirect(url_for('index'))
            else:
                return "<script>alert('아이디 또는 비밀번호가 틀렸습니다.'); history.back();</script>"
    finally:
        conn.close()


@app.route('/logout')
def logout():
    session.clear()  # 세션 비우기
    return redirect(url_for('login'))


@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'GET':
        return render_template('join.html')

    uid = request.form.get('uid')
    password = request.form.get('password')  # 컬럼명 password에 맞춤
    name = request.form.get('name')

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 아이디 중복 확인
            cursor.execute("SELECT id FROM members WHERE uid = %s", (uid,))
            if cursor.fetchone():
                return "<script>alert('이미 존재하는 아이디입니다.'); history.back();</script>"

            # 회원 정보 저장 (role, active는 기본값이 들어감)
            sql = "INSERT INTO members (uid, password, name) VALUES (%s, %s, %s)"
            cursor.execute(sql, (uid, password, name))
            conn.commit()

            return "<script>alert('회원가입이 완료되었습니다!'); location.href='/login';</script>"
    except Exception as e:
        print(f"회원가입 에러: {e}")
        return "가입 중 오류가 발생했습니다."
    finally:
        conn.close()


@app.route('/member/edit', methods=['GET', 'POST'])
def member_edit():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            if request.method == 'GET':
                # 기존 정보 불러오기
                cursor.execute("SELECT * FROM members WHERE id = %s", (session['user_id'],))
                user_info = cursor.fetchone()
                return render_template('member_edit.html', user=user_info)

            # POST 요청: 정보 업데이트
            new_name = request.form.get('name')
            new_pw = request.form.get('password')

            if new_pw:  # 비밀번호 입력 시에만 변경
                sql = "UPDATE members SET password = %s WHERE id = %s"
                cursor.execute(sql, (new_pw, session['user_id']))
            else:  # 이름만 변경
                sql = "UPDATE members SET name = %s WHERE id = %s"
                cursor.execute(sql, (new_name, session['user_id']))

            conn.commit()
            session['user_name'] = new_name  # 세션 이름 정보도 갱신
            return "<script>alert('정보가 수정되었습니다.'); location.href='/mypage';</script>"
    finally:
        conn.close()



@app.route('/mypage')
def mypage():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 내 상세 정보 조회
            cursor.execute("SELECT * FROM members WHERE id = %s", (session['user_id'],))
            user_info = cursor.fetchone()

            # 2. 내가 쓴 게시글 개수 조회 (작성하신 boards 테이블 활용)
            cursor.execute("SELECT COUNT(*) as board_count FROM boards WHERE member_id = %s", (session['user_id'],))
            board_count = cursor.fetchone()['board_count']

            return render_template('mypage.html', user=user_info, board_count=board_count)
    finally:
        conn.close()

# @app.route('/score/members')
# def score_member_list():
#     # 관리자나 매니저만 접근 가능
#     if session.get('user_role') not in ('admin', 'manager'):
#         return "<script>alert('권한이 없습니다.'); history.back();</script>"
#
#     conn = Session.get_connection()
#     try:
#         with conn.cursor() as cursor:
#             # 일반 유저(student)들만 조회
#             sql = "SELECT id, uid, name FROM members WHERE role = 'user' AND active = 1"
#             cursor.execute(sql)
#             students = cursor.fetchall()
#             return render_template('score_member_list.html', students=students)
#     finally:
#         conn.close()

@app.route('/score/members')
def score_members():
    if session.get('user_role') not in ('admin', 'manager'):
        return "<script>alert('권한이 없습니다.'); history.back();</script>"

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # LEFT JOIN을 통해 성적이 있으면 s.id가 숫자로, 없으면 NULL로 나옵니다.
            sql = """
                SELECT m.id, m.uid, m.name, s.id AS score_id 
                FROM members m
                LEFT JOIN scores s ON m.id = s.member_id
                WHERE m.role = 'user'
                ORDER BY m.name ASC
            """
            cursor.execute(sql)
            members = cursor.fetchall()
            return render_template('score_member_list.html', members=members)
    finally:
        conn.close()

# @app.route('/score/add')
# def score_add():
#     # 관리자/매니저 권한 체크
#     if session.get('user_role') not in ('admin', 'manager'):
#         return "<script>alert('권한이 없습니다.'); history.back();</script>"
#
#     # URL 파라미터(?uid=abc&name=홍길동) 받기
#     target_uid = request.args.get('uid')
#     target_name = request.args.get('name')
#
#     return render_template('score_form.html', target_uid=target_uid, target_name=target_name)


@app.route('/score/add')
def score_add():
    if session.get('user_role') not in ('admin', 'manager'):
        return "<script>alert('권한이 없습니다.'); history.back();</script>"

    target_uid = request.args.get('uid')
    target_name = request.args.get('name')

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 대상 학생의 id 찾기
            cursor.execute("SELECT id FROM members WHERE uid = %s", (target_uid,))
            student = cursor.fetchone()

            # 2. 기존 성적이 있는지 조회
            existing_score = None
            if student:
                cursor.execute("SELECT * FROM scores WHERE member_id = %s", (student['id'],))
                row = cursor.fetchone()
                if row:
                    # 기존에 만든 Score.from_db 활용
                    existing_score = Score.from_db(row)

            return render_template('score_form.html',
                                   target_uid=target_uid,
                                   target_name=target_name,
                                   score=existing_score)  # score 객체 전달
    finally:
        conn.close()

@app.route('/score/save', methods=['POST'])
def score_save():
    if session.get('user_role') not in ('admin', 'manager'):
        return "권한 오류", 403

    # 폼 데이터 수집
    target_uid = request.form.get('target_uid')
    kor = int(request.form.get('korean', 0))
    eng = int(request.form.get('english', 0))
    math = int(request.form.get('math', 0))

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 대상 학생의 id(PK) 가져오기
            cursor.execute("SELECT id FROM members WHERE uid = %s", (target_uid,))
            student = cursor.fetchone()
            if not student:
                return "<script>alert('존재하지 않는 학생입니다.'); history.back();</script>"

            # 2. Score 객체 생성 (계산 프로퍼티 활용)
            temp_score = Score(member_id=student['id'], kor=kor, eng=eng, math=math)

            # 3. 기존 데이터가 있는지 확인 (ScoreService 로직 이식)
            cursor.execute("SELECT id FROM scores WHERE member_id = %s", (student['id'],))
            is_exist = cursor.fetchone()

            if is_exist:
                # UPDATE 실행
                sql = """
                    UPDATE scores SET korean=%s, english=%s, math=%s, 
                                      total=%s, average=%s, grade=%s
                    WHERE member_id = %s
                """
                cursor.execute(sql, (temp_score.kor, temp_score.eng, temp_score.math,
                                     temp_score.total, temp_score.avg, temp_score.grade,
                                     student['id']))
            else:
                # INSERT 실행
                sql = """
                    INSERT INTO scores (member_id, korean, english, math, total, average, grade)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (student['id'], temp_score.kor, temp_score.eng, temp_score.math,
                                     temp_score.total, temp_score.avg, temp_score.grade))

            conn.commit()
            return f"<script>alert('{target_uid} 학생 성적 저장 완료!'); location.href='/score/list';</script>"
    finally:
        conn.close()


@app.route('/score/list')
def score_list():
    # 1. 권한 체크 (관리자나 매니저만 볼 수 있게 설정)
    if session.get('user_role') not in ('admin', 'manager'):
        return "<script>alert('권한이 없습니다.'); history.back();</script>"

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 2. JOIN을 사용하여 학생 이름(name)과 성적 데이터를 함께 조회
            # 성적이 없는 학생은 제외하고, 성적이 있는 학생들만 총점 순으로 정렬
            sql = """
                SELECT m.name, m.uid, s.* FROM scores s
                JOIN members m ON s.member_id = m.id
                ORDER BY s.total DESC
            """
            cursor.execute(sql)
            datas = cursor.fetchall()

            # 3. DB에서 가져온 딕셔너리 리스트를 Score 객체 리스트로 변환
            score_objects = []
            for data in datas:
                # Score 클래스에 정의하신 from_db 활용
                s = Score.from_db(data)
                # 객체에 없는 이름(name) 정보는 수동으로 살짝 넣어주기
                s.name = data['name']
                s.uid = data['uid']
                score_objects.append(s)

            return render_template('score_list.html', scores=score_objects)
    finally:
        conn.close()

@app.route('/score/my')
def score_my():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 내 ID로만 조회
            sql = "SELECT * FROM scores WHERE member_id = %s"
            cursor.execute(sql, (session['user_id'],))
            row = cursor.fetchone()

            # Score 객체로 변환 (from_db 활용)
            score = Score.from_db(row) if row else None

            return render_template('score_my.html', score=score)
    finally:
        conn.close()



@app.route('/board/my')
def board_my_list():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = Session.get_connection()
    try:
        with conn.cursor() as cursor:
            # 내가 작성한 글만 최신순으로 조회
            sql = "SELECT * FROM boards WHERE member_id = %s ORDER BY created_at DESC"
            cursor.execute(sql, (session['user_id'],))
            my_posts = cursor.fetchall()

            return render_template('board_my_list.html', posts=my_posts)
    finally:
        conn.close()


#  -- 1. 게시글 본문 테이블
# CREATE TABLE posts (
    # id INT AUTO_INCREMENT PRIMARY KEY,
    # member_id INT NOT NULL,           -- 작성자 (members 테이블 외래키)
    # title VARCHAR(200) NOT NULL,
    # content TEXT NOT NULL,
    # view_count INT DEFAULT 0,         -- 조회수 추가
    # created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    # updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    # FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
# );

# -- 2. 첨부파일 관리 테이블
# CREATE TABLE attachments (
    # id INT AUTO_INCREMENT PRIMARY KEY,
    # post_id INT NOT NULL,             -- 어떤 게시글의 파일인지
    # origin_name VARCHAR(255) NOT NULL, -- 사용자가 올린 실제 파일명
    # save_name VARCHAR(255) NOT NULL,   -- 서버에 저장된 고유 파일명 (중복방지)
    # file_path VARCHAR(500) NOT NULL,   -- 저장된 경로
    # file_size INT,                    -- 파일 용량(Byte)
    # created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    # FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
# );

# 파일 게시판 목록
@app.route('/filesboard')
def filesboard_list():
    posts = PostService.get_posts()
    return render_template('filesboard_list.html', posts=posts)


# 파일 게시판 상세 보기
@app.route('/filesboard/view/<int:post_id>')
def filesboard_view(post_id):
    post, files = PostService.get_post_detail(post_id)
    if not post:
        return "<script>alert('해당 게시글이 없습니다.'); location.href='/filesboard';</script>"
    return render_template('filesboard_view.html', post=post, files=files)

# send_from_directory 사용하여 자료 다운로드 가능
@app.route('/download/<path:filename>')
def download_file(filename):
    # 파일이 저장된 폴더(uploads)에서 파일을 찾아 전송합니다.
    # 프론트 <a href="{{ url_for('download_file', filename=file.save_name) }}" ...> 이부분 처리용
    # filename은 서버에 저장된 save_name입니다.
    # 브라우저가 다운로드할 때 보여줄 원본 이름을 쿼리 스트링으로 받거나 DB에서 가져와야 합니다.
    origin_name = request.args.get('origin_name')
    return send_from_directory('uploads/', filename, as_attachment=True, download_name=origin_name)
    #   return send_from_directory('uploads/', filename)는 브라우져에서 바로 열어버림
    #   as_attachment=True 로 하면 파일 다운로드 창을 띄움
    #   저장할 파일명은 download_name=origin_name 로 지정

# 단일 파일 게시글 쓰기 (GET: 폼 보여주기, POST: 저장 처리)
# @app.route('/filesboard/write', methods=['GET', 'POST'])
# def filesboard_write():
#     if 'user_id' not in session:
#     return redirect(url_for('login'))
#
# if request.method == 'POST':
#         title = request.form.get('title')
#         content = request.form.get('content')
#         file = request.files.get('file')
#
#         if PostService.save_post(session['user_id'], title, content, file):
#       return "<script>alert('게시글이 등록되었습니다.'); location.href='/filesboard';</script>"
#         else:
#             return "<script>alert('등록 실패'); history.back();</script>"
#
# return render_template('filesboard_write.html')

# 다중 파일 처리용
@app.route('/filesboard/write', methods=['GET', 'POST'])
def filesboard_write():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        # 핵심: getlist를 사용해야 리스트 형태로 가져옵니다.
        files = request.files.getlist('files')

        if PostService.save_post(session['user_id'], title, content, files):
            return "<script>alert('게시글이 등록되었습니다.'); location.href='/filesboard';</script>"
        else:
            return "<script>alert('등록 실패'); history.back();</script>"

    return render_template('filesboard_write.html')

# 단일 파일 게시글 수정용
# @app.route('/filesboard/edit/<int:post_id>', methods=['GET', 'POST'])
# def filesboard_edit(post_id):
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
#
#     if request.method == 'POST':
#         title = request.form.get('title')
#         content = request.form.get('content')
#         file = request.files.get('file')
#
#         if PostService.update_post(post_id, title, content, file):
#             return f"<script>alert('수정되었습니다.'); location.href='/filesboard/view/{post_id}';</script>"
#         return "<script>alert('수정 실패'); history.back();</script>"
#
#     # GET: 기존 데이터 불러오기
#     post, files = PostService.get_post_detail(post_id)
#     # 본인 확인 로직 추가
#     if post['member_id'] != session['user_id']:
#         return "<script>alert('권한이 없습니다.'); history.back();</script>"
#
#     return render_template('filesboard_edit.html', post=post, files=files)

# 다중파일 수정용
@app.route('/filesboard/edit/<int:post_id>', methods=['GET', 'POST'])
def filesboard_edit(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        files = request.files.getlist('files')  # 다중 파일 가져오기

        if PostService.update_post(post_id, title, content, files):
            return f"<script>alert('수정되었습니다.'); location.href='/filesboard/view/{post_id}';</script>"
        return "<script>alert('수정 실패'); history.back();</script>"

    # GET 요청 시 기존 데이터 로드
    post, files = PostService.get_post_detail(post_id)
    if post['member_id'] != session['user_id']:
        return "<script>alert('권한이 없습니다.'); history.back();</script>"

    return render_template('filesboard_edit.html', post=post, files=files)

@app.route('/filesboard/delete/<int:post_id>')
def filesboard_delete(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 삭제 전 작성자 확인을 위해 정보 조회
    post, _ = PostService.get_post_detail(post_id)
    # _은 리턴값을 사용하지 않겠다 라는 관례적인 표현 (_) 사용하지 않는 변수

    if not post:
        return "<script>alert('이미 삭제된 게시글입니다.'); location.href='/filesboard';</script>"

    # 본인 확인 (또는 관리자 권한)
    if post['member_id'] != session['user_id'] and session.get('user_role') != 'admin':
        return "<script>alert('삭제 권한이 없습니다.'); history.back();</script>"

    if PostService.delete_post(post_id):
        return "<script>alert('성공적으로 삭제되었습니다.'); location.href='/filesboard';</script>"
    else:
        return "<script>alert('삭제 중 오류가 발생했습니다.'); history.back();</script>"

##################################################################################################
# 1. 상품 이미지 전용 경로 설정
ITEM_UPLOAD_FOLDER = os.path.join(app.config['UPLOAD_FOLDER'], 'item')

# 폴더가 없으면 자동 생성 (uploads/item)
if not os.path.exists(ITEM_UPLOAD_FOLDER):
    os.makedirs(ITEM_UPLOAD_FOLDER)

product_service = ProductService()

@app.route('/items/register', methods=['GET', 'POST'])
def register_item():
    # 1. POST 방식: 실제 등록 로직 처리
    if request.method == 'POST':
        # 이미지 파일 처리
        files = request.files.getlist('images')
        image_filenames = []
        ITEM_UPLOAD_FOLDER = os.path.join(app.config['UPLOAD_FOLDER'], 'item')

        for file in files:
            if file and file.filename:
                filename = f"item_{uuid4().hex}_{file.filename}"
                file_path = os.path.join(ITEM_UPLOAD_FOLDER, filename)
                file.save(file_path)
                image_filenames.append(f"item/{filename}")

        # 서비스 호출 (Item 객체 생성 및 DB 저장)
        new_item = ProductService.create_item_from_form(request.form)
        success = product_service.register_product(new_item, image_filenames)

        if success:
            return redirect(url_for('item_list'))
        else:
            return "상품 등록에 실패했습니다.", 500

    # 2. GET 방식: 등록 폼 화면 보여주기
    # templates/item/register.html 경로를 사용합니다.
    return render_template('item/register.html', categories=Item.CATEGORIES)


@app.route('/items')
def item_list():
    """상품 목록 페이지"""
    # 1. ProductService의 정적 메서드를 호출하여 상품 리스트를 가져옵니다.
    # (대표 이미지 경로인 main_image가 포함된 Item 객체 리스트입니다.)
    items = product_service.get_all_products()

    # 2. 미리 만들어둔 상품 목록 템플릿으로 데이터를 전달합니다.
    return render_template('item/list.html', items=items)

# 현재 HTML은 /uploads/item/파일명.jpg를 요청하고 있습니다.
# 하지만 Flask는 기본적으로 static 폴더 외에는 보안상 접근을 차단합니다.
# 위와 같이 @app.route('/uploads/<path:filename>')를 정의해 줘야만,
# Flask가 "아, /uploads/로 시작하는 요청은 uploads 폴더 안에서 파일을 찾아 보내주라는 거구나!"라고 이해합니다.

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    # 실제 파일이 들어있는 폴더 경로 (프로젝트 루트의 uploads 폴더)
    upload_path = os.path.join(os.getcwd(), 'uploads')
    return send_from_directory(upload_path, filename)


@app.route('/items/<int:item_id>')
def item_detail(item_id):
    """상품 상세 페이지"""
    item = ProductService.get_product_by_id(item_id)

    if not item:
        return "상품을 찾을 수 없습니다.", 404

    return render_template('item/detail.html', item=item)


@app.route('/items/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = ProductService.get_product_by_id(item_id)

    if request.method == 'POST':
        item_data = {
            'name': request.form['name'],
            'price': int(request.form['price']),
            'stock': int(request.form['stock']),
            'category': request.form['category'],
            'code': request.form['code']
        }

        new_img_paths = []
        files = request.files.getlist('images')

        for file in files:
            if file and file.filename:
                # 1. 원본 파일의 확장자 추출
                ext = os.path.splitext(file.filename)[1]
                # 2. UUID로 고유한 파일명 생성
                new_filename = f"{uuid.uuid4()}{ext}"

                # 3. 저장 경로 설정 및 저장
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'item', new_filename)
                file.save(file_path)

                # 4. DB에 들어갈 상대 경로 저장
                new_img_paths.append(f"item/{new_filename}")

        if ProductService.update_product(item_id, item_data, new_img_paths):
            return f"<script>alert('수정되었습니다.'); location.href='/items/{item_id}';</script>"
        else:
            return "<script>alert('수정 실패'); history.back();</script>"

    return render_template('item/edit.html', item=item)


@app.route('/items/delete/<int:item_id>')
def delete_item(item_id):
    # 권한 체크 (admin, manager)
    if session.get('user_role') not in ['admin', 'manager']:
        return "<script>alert('권한이 없습니다.'); history.back();</script>"

    # DB 삭제 및 삭제된 이미지 경로 리스트 가져오기
    success, image_list = ProductService.delete_product_with_files(item_id)

    if success:
        # 실제 서버 파일 삭제
        for img in image_list:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], img['image_path'])
            if os.path.exists(file_path):
                os.remove(file_path)

        return "<script>alert('상품과 관련된 모든 정보가 삭제되었습니다.'); location.href='/items';</script>"
    else:
        return "<script>alert('삭제 중 오류가 발생했습니다.'); history.back();</script>"

##########################################################################################################
# 장바구니는 쿠키를사용 한다. (쿠키는 브라우져에 저장되는 데이터)
@app.route('/cart/add/<int:item_id>', methods=['POST'])
def add_to_cart(item_id):
    quantity = int(request.form.get('quantity', 1)) # 뒤에 ,1은 기본값 데이터가 안넘어왔을 때 처리용

    # 1. 기존 쿠키에서 장바구니 가져오기
    cart_cookie = request.cookies.get('cart')
    if cart_cookie:
        cart = json.loads(cart_cookie)  # 문자열을 딕셔너리로 변환
    else:
        cart = {}

    # 2. 수량 업데이트
    item_id_str = str(item_id)
    if item_id_str in cart:
        cart[item_id_str] += quantity
    else:
        cart[item_id_str] = quantity

    # 3. 응답 객체 생성 및 쿠키 설정 from flask import make_response
    res = make_response(f"<script>alert('장바구니에 담겼습니다!'); location.href='/items';</script>")

    # JSON으로 다시 변환하여 쿠키에 저장 (유효기간 3일 설정)
    res.set_cookie('cart', json.dumps(cart), max_age=60 * 60 * 24 * 3)

    return res



@app.route('/cart')
def view_cart():
    cart_cookie = request.cookies.get('cart')
    cart_items = []
    total_price = 0

    if cart_cookie:
        cart = json.loads(cart_cookie)
        for item_id, quantity in cart.items():
            # 이전에 만든 정적 메서드 활용
            item = ProductService.get_product_by_id(int(item_id))
            if item:
                item.order_qty = quantity  # 수량 추가
                item.subtotal = item.price * quantity
                cart_items.append(item)
                total_price += item.subtotal

    return render_template('item/cart.html', cart_items=cart_items, total_price=total_price)


@app.route('/cart/delete/<int:item_id>')
def delete_cart_item(item_id):
    cart_cookie = request.cookies.get('cart')
    if not cart_cookie:
        return redirect(url_for('view_cart'))

    cart = json.loads(cart_cookie)
    item_id_str = str(item_id)

    if item_id_str in cart:
        cart.pop(item_id_str)  # 해당 상품 삭제

    res = make_response(redirect(url_for('view_cart')))
    # 업데이트된 장바구니를 다시 쿠키에 저장
    res.set_cookie('cart', json.dumps(cart), max_age=60 * 60 * 24 * 3)
    return res

# 쿠키 사용 시 주의점 (꿀팁)
# 용량 제한: 쿠키는 보통 4KB가 한계입니다. 상품을 수백 개 담는 게 아니라면 충분하지만, 너무 많은 데이터를 담으면 안 됩니다.
#
# 보안: 쿠키는 사용자가 직접 값을 수정할 수 있습니다.
# 그래서 **결제 단계(주문하기)**에서는 반드시 쿠키의 가격 정보를 믿지 말고,
# DB에서 실제 가격을 다시 조회해서 계산해야 합니다. (우리가 만든 OrderService 방식처럼요!)
############################################################################################################

@app.route('/order/<int:item_id>', methods=['POST'])
def place_order(item_id):
    # 로그인 기능을 아직 안 붙였다면 임시로 member_id = 1 사용
    # 실제로는 session.get('member_id') 등을 사용합니다.
    member_id = session.get('user_id')
    quantity = int(request.form.get('quantity', 1)) # 뒤에 ,1은 기본값 데이터가 안넘어왔을 때 처리용

    success, message = OrderService.create_order(member_id, item_id, quantity)

    if success:
        # 주문 성공 시 주문 내역 페이지나 상품 목록으로 이동
        return f"<script>alert('{message}'); location.href='/items';</script>"
    else:
        return f"<script>alert('{message}'); history.back();</script>"


@app.route('/order/checkout', methods=['POST'])
def checkout():
    # 1. 쿠키에서 장바구니 데이터 읽기
    cart_cookie = request.cookies.get('cart')
    if not cart_cookie:
        return "<script>alert('주문할 상품이 없습니다.'); history.back();</script>"

    cart_data = json.loads(cart_cookie)
    member_id = session['user_id']  # 테스트용 임시 ID

    # 2. 주문 서비스 호출
    success, message = OrderService.checkout(member_id, cart_data)

    if success:
        # 주문 성공 시 쿠키 삭제 후 이동
        res = make_response(f"<script>alert('{message}'); location.href='/items';</script>")
        res.set_cookie('cart', '', max_age=0)  # 쿠키 비우기
        return res
    else:
        return f"<script>alert('{message}'); history.back();</script>"
#################################################################################################################

@app.route('/order/<int:item_id>', methods=['POST'])
def place_order_direct(item_id):
    # 1. 상세 페이지 폼에서 선택한 수량 가져오기
    quantity = int(request.form.get('quantity', 1))
    member_id = session.get('user_id')  # 테스트용 임시 ID

    # 2. 단일 상품 주문을 위해 데이터를 딕셔너리 형태로 변환 (OrderService.checkout 구조 활용)
    # OrderService.checkout은 {item_id: quantity} 형태의 cart_data를 받습니다.
    direct_cart_data = {str(item_id): quantity}

    # 3. 주문 서비스 호출
    success, message = OrderService.checkout(member_id, direct_cart_data)

    if success:
        # 바로 구매 성공 시 주문 완료 알림 후 상품 목록으로 이동
        return f"<script>alert('{message}'); location.href='/items';</script>"
    else:
        # 재고 부족 등 실패 시 이전 페이지로
        return f"<script>alert('{message}'); history.back();</script>"


@app.route('/orders')
def order_list():
    member_id = session.get('user_id')
    if not member_id:
        return "<script>alert('로그인이 필요합니다.'); location.href='/login';</script>"

    orders = OrderService.get_member_orders(member_id)
    return render_template('order/list.html', orders=orders)


@app.route('/orders/<int:order_id>')
def order_detail(order_id):
    member_id = session.get('user_id')
    if not member_id:
        return redirect(url_for('login'))

    order, items = OrderService.get_order_detail(order_id, member_id)

    if not order:
        return "<script>alert('주문 내역을 찾을 수 없습니다.'); history.back();</script>"

    return render_template('order/detail.html', order=order, items=items)

#########################################주문내역 end###################################################################
########################################## AiDetect 시작 #########################################################

# CREATE TABLE ai_detect_posts (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     member_id INT,
#     title VARCHAR(255),
#     content TEXT,
#     image_path VARCHAR(255),
#     detect_result TEXT, -- YOLO 탐지 결과(객체 이름 등)를 저장
#     created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
#     FOREIGN KEY (member_id) REFERENCES members(id)
# );

import uuid
import os
import json
from ultralytics import YOLO # pip install ultralytics
from LMS.service.AiDetectService import AiDetectService

# 모델 로드
model = YOLO('yolov8n.pt')
model.to('cuda') # gpu 처리용 

@app.route('/ai-detect', methods=['GET', 'POST'])
def ai_detect_board():
    if request.method == 'POST':
        # 1. 파일 저장
        file = request.files['image']
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ai_detect', filename)
        file.save(save_path)

        # 2. YOLO 객체 탐지
        results = model.predict(save_path)
        detected_names = [model.names[int(box.cls[0])] for box in results[0].boxes]

        # 3. DB 저장
        AiDetectService.save_detect_post(
            session['user_id'],
            request.form['title'],
            request.form['content'],
            f"ai_detect/{filename}",
            json.dumps(detected_names)
        )
        return redirect(url_for('ai_detect_board'))

    posts = AiDetectService.get_all_posts()
    return render_template('ai_detect/list.html', posts=posts)

# 이미지박싱 처리용 라이브러리 설치 pip install opencv-python
import cv2  # OpenCV 추가
import numpy as np

# ai_detect 전용 폴더 자동 생성 추가
ai_detect_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ai_detect')
if not os.path.exists(ai_detect_path):
    os.makedirs(ai_detect_path)

import json

# jinja2에서 json 문자열을 객체로 변환하는 필터 등록
@app.template_filter('from_json')
def from_json_filter(value):
    return json.loads(value) if value else []

@app.route('/ai-detect/write', methods=['GET', 'POST'])
def write_ai_detect():


    if request.method == 'POST':
        file = request.files['image']
        if file and file.filename:
            # 파일명 생성 (UUID)
            ext = os.path.splitext(file.filename)[1]
            filename = f"{uuid.uuid4()}{ext}"

            # 원본 저장 경로 (save_path 정의)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ai_detect', filename)
            file.save(save_path)

            # # 1. YOLO 예측 및 박싱 처리
            results = model.predict(save_path)

            # # 2. 박스가 그려진 이미지 생성 및 저장
            res_plotted = results[0].plot()
            annotated_filename = f"box_{filename}"
            annotated_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ai_detect', annotated_filename)
            cv2.imwrite(annotated_path, res_plotted)

            # 3. 상세 탐지 결과 추출 (박스 좌표 포함)
            detailed_results = []
            detected_names = []  # DB 저장용 리스트
            for box in results[0].boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                name = model.names[cls]
                coords = box.xyxy[0].tolist()

                detected_names.append(name)  # 이름 추가
                detailed_results.append({
                    'name': name,
                    'conf': round(conf * 100, 2),
                    'bbox': [round(x, 1) for x in coords]
                })

            # 4. DB 저장 (기존과 동일하게 name 리스트만 저장하거나 상세 내용을 JSON으로 저장)
            AiDetectService.save_detect_post(
                session.get('user_id'),
                request.form['title'],
                request.form['content'],
                f"ai_detect/{filename}",
                json.dumps(detailed_results)  # detailed_results를 저장하세요!
            )

            return render_template('ai_detect/result.html',
                                   img_url=f"ai_detect/{annotated_filename}",
                                   results=detailed_results)  # tags 대신 results 전달

    return render_template('ai_detect/write.html')


@app.route('/ai-detect/view/<int:post_id>')
def ai_detect_view(post_id):

    # 1. DB에서 해당 ID의 게시글 가져오기
    conn = Session.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_detect_posts WHERE id = %s", (post_id,))
    post = cursor.fetchone()
    cursor.close()
    conn.close()

    if not post:
        return "<script>alert('해당 기록을 찾을 수 없습니다.'); history.back();</script>"

    # 2. 이미지 경로 처리 (리스트와 마찬가지로 box_ 붙은 이미지 표시)
    saved_results = json.loads(post['detect_result']) if post['detect_result'] else []

    path_parts = post['image_path'].split('/')
    annotated_url = f"{path_parts[0]}/box_{path_parts[1]}"

    return render_template('ai_detect/result.html',
                           img_url=annotated_url,
                           results=saved_results,  # 이름을 results로 통일!
                           post=post)



#################################################YOLO 이미지 객체 탐지 END######################################################################
#################################################YOLO 영상 객체 탐지 END######################################################################

# -- 1. 영상 게시글 및 상태 관리 테이블
# CREATE TABLE ai_video_posts (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     member_id INT,                        -- members 테이블의 id가 INT이므로 동일하게 설정
#     title VARCHAR(255) NOT NULL,
#     content TEXT,
#     origin_video_path VARCHAR(255),       -- 원본 영상 경로
#     result_video_path VARCHAR(255),       -- 박싱 처리된 영상 경로
#     status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED, FAILED
#     total_frames INT DEFAULT 0,           -- 총 프레임 수
#     created_at DATETIME DEFAULT NOW(),
#     -- member_id 타입이 INT이므로 정상적으로 연결됩니다.
#     FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
# );
#
# -- 2. 영상 프레임별 상세 탐지 결과 테이블
# CREATE TABLE ai_video_details (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     video_post_id INT,                    -- ai_video_posts 테이블 참조
#     frame_number INT,                     -- 프레임 번호 (타임라인용)
#     detected_objects JSON,                -- 해당 시점의 객체 정보 [ {"name":"car", "conf":0.9}, ... ]
#     FOREIGN KEY (video_post_id) REFERENCES ai_video_posts(id) ON DELETE CASCADE
# );

# service/AiVideoService.py에 핵심로직 구현

import cv2
import json
import os
from LMS.service.AiVideoService import AiVideoService
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB까지 허용

# 전역 변수: 진행률 관리
analysis_status = {}


@app.route('/ai-detect/progress')
def get_progress():
    uid = request.args.get('user_id')
    # 해당 유저의 진행 상태를 반환
    return jsonify(analysis_status.get(uid, {'percent': 0, 'message': '대기 중...'}))



# 1. 영상 탐지 목록 (이미지와 분리해서 관리하거나 같이 관리 가능)
@app.route('/ai-detect/video')
def video_list():
    conn = Session.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_video_posts ORDER BY created_at DESC")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('ai_detect/video_list.html', posts=posts)


# 2. 영상 업로드 페이지
@app.route('/ai-detect/video/write')
def write_video_form():
    return render_template('ai_detect/video_write.html')


def process_video_ai(video_post_id, origin_path, filename, target_user_id=None):
    cap = cv2.VideoCapture(origin_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    # FPS 방어 코드
    if fps == 0:
        fps = 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # output_filename = f"res_{filename.split('.')[0]}.mp4" 도커용으로 변경
    output_filename = f"res_{filename.split('.')[0]}.avi"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ai_detect', output_filename)



    # fourcc = cv2.VideoWriter_fourcc(*'avc1') 도커용으로 변경
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # 유튜브는 50%부터, 일반 업로드는 10%부터 시작하도록 유동적 설정
    start_p = 0
    if target_user_id and target_user_id in analysis_status:
        start_p = analysis_status[target_user_id].get('percent', 0)


    frame_count = 0
    batch_frames = []
    batch_size = 16   # GPU 효율 핵심 8~16~24~32



    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        # 프레임 스킵 (속도 2~3배짜리)
        if frame_count % 3 != 0:
            frame_count += 1
            continue

        batch_frames.append(frame) # 배치용 프레임


        if len(batch_frames) == batch_size:
            results = model.predict(batch_frames, device=0, verbose=False)

            for i, r in enumerate(results):
                detected_objects = []

                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = model.names[cls]
                    coords = box.xyxy[0].tolist()

                    detected_objects.append({
                        'name': name,
                        'conf': round(conf, 2),
                        'bbox': [round(x, 1) for x in coords]
                    })

                # DB 저장 (간격 유지)
                if frame_count % 10 == 0:
                    AiVideoService.save_video_detail(
                        video_post_id,
                        frame_count,
                        detected_objects
                    )

                # plot 최소화 가능 (성능 중요하면 frame으로 변경)
                out.write(r.plot())
                # out.write(frame) 프레임 처리했더니 라운드박스 안보임

                frame_count += 1

                # 진행률 업데이트
                if target_user_id and total_frames > 0:
                    current_p = start_p + (frame_count / total_frames * (100 - start_p))
                    analysis_status[target_user_id] = {
                        'percent': round(current_p, 1),
                        'message': f'AI 분석 중... ({frame_count}/{total_frames})'
                    }

            batch_frames = []

    cap.release()
    out.release()

    # avi를 mp4로 변환 도커용
    mp4_path = output_path.replace('.avi', '.mp4')
    os.system(f"ffmpeg -y -i {output_path} -vcodec libx264 -preset ultrafast {mp4_path}")

    # avi 삭제 (용량 절약)
    os.remove(output_path)

    # DB 업데이트 (mp4 기준)
    mp4_filename = os.path.basename(mp4_path)

    AiVideoService.update_video_status(
        video_post_id,
        'COMPLETED',
        f"ai_detect/{mp4_filename}",
        total_frames
    )
    if target_user_id:
        analysis_status[target_user_id] = {'percent': 100, 'message': '모든 분석이 완료되었습니다!'}


# --- [일반 동영상 업로드 라우트] ---
@app.route('/ai-detect/video/process', methods=['POST'])
def process_video_ai_route():
    if 'video' not in request.files:
        return jsonify({"status": "fail", "msg": "파일이 없습니다."})

    file = request.files['video']
    title = request.form.get('title')
    content = request.form.get('content')
    user_id = request.form.get('user_id')  # 프론트엔드 fetch에서 보낸 ID

    if file and file.filename:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        origin_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ai_detect', filename)
        file.save(origin_path)

        video_post_id = AiVideoService.create_video_post(
            user_id, title, content, f"ai_detect/{filename}"
        )

        if video_post_id:
            # 일반 업로드는 분석 비중이 크므로 10%부터 시작
            analysis_status[user_id] = {'percent': 10, 'message': '업로드 완료! 분석을 시작합니다.'}

            # 스레드로 실행하여 즉시 응답 반환
            thread = threading.Thread(target=process_video_ai, args=(video_post_id, origin_path, filename, user_id))
            thread.start()

            return jsonify({"status": "success", "post_id": video_post_id})

    return jsonify({"status": "fail", "msg": "분석 요청 실패"})


@app.route('/ai-video/view/<int:post_id>')
def view_video(post_id):
    conn = Session.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_video_posts WHERE id = %s", (post_id,))
    post = cursor.fetchone()
    cursor.execute("SELECT frame_number, detected_objects FROM ai_video_details WHERE video_post_id = %s ORDER BY frame_number", (post_id,))
    details = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('ai_detect/view_video.html', post=post, details=details)
#######################################  동영상 처리 AI END ####################################################
######################################## 유튜브 동영상 객체 탐지 ################################################
# app.py
import yt_dlp # pip install yt-dlp

# 진행률 게이지용 전역 변수
analysis_status = {}



def make_yt_hook(user_id):
    def hook(d):
        if d['status'] == 'downloading':
            p_str = d.get('_percent_str', '0%').replace('%', '').strip()
            try:
                p_float = float(p_str)
                # 다운로드 단계: 0 ~ 50% 구간
                analysis_status[user_id] = {
                    'percent': round(p_float * 0.5, 1),
                    'message': f'유튜브 영상을 가져오는 중... ({p_str}%)'
                }
            except:
                pass

    return hook


def start_analysis_thread(yt_url, video_post_id, save_path, filename, user_id):
    try:
        # 1. 유튜브 다운로드 (오디오 제외 옵션 유지)
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]/best[ext=mp4]/best',
            'outtmpl': save_path,
            'noplaylist': True,
            'progress_hooks': [make_yt_hook(user_id)],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([yt_url])

        # 2. AI 영상 분석 (50 ~ 100% 구간은 process_video_ai 내부에서 업데이트)
        # 괄호 안에 user_id 인자를 추가하여 호출합니다.
        process_video_ai(video_post_id, save_path, filename, user_id)

    except Exception as e:
        print(f"분석 스레드 에러: {e}")
        analysis_status[user_id] = {'percent': 0, 'message': '분석 중 오류가 발생했습니다.'}

@app.route('/ai-detect/youtube/write')
def youtube_write_form():
    return render_template('ai_detect/youtube_write.html')

@app.route('/ai-detect/youtube/process', methods=['POST'])
def process_youtube_route():
    yt_url = request.form.get('yt_url')
    title = request.form.get('title')
    content = request.form.get('content')
    user_id = request.form.get('user_id') # 프론트에서 보낸 ID

    filename = f"yt_{uuid.uuid4()}.mp4"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ai_detect', filename)

    # 1. DB에 PENDING 상태로 먼저 저장
    video_post_id = AiVideoService.create_video_post(
        user_id, title, content, f"ai_detect/{filename}"
    )

    if video_post_id:
        # 2. 초기 상태 설정 (유튜브는 다운로드부터 시작하므로 1% 설정)
        analysis_status[user_id] = {'percent': 1, 'message': '유튜브 연결 중...'}

        # 3. 🔥 백그라운드 스레드 실행 (다운로드 + 분석 통합 함수)
        # 이전에 만든 start_analysis_thread 함수를 호출합니다.
        thread = threading.Thread(
            target=start_analysis_thread,
            args=(yt_url, video_post_id, save_path, filename, user_id)
        )
        thread.start()

        # 4. ✨ 중요: 리다이렉트가 아닌 JSON 반환!
        return jsonify({"status": "success", "post_id": video_post_id})

    return jsonify({"status": "fail", "msg": "DB 등록 실패"})


######################################################### 유튜브 처리 완료 ##################################################################

@app.route('/')
def index():
    return render_template('main.html')

# 스트림 처리와 스레드 처리용으로 변환 
# if __name__ == '__main__':
#    #app.run(debug=True)
#    app.run(host='0.0.0.0', port=5000, debug=True)

######################################################### ipcam 스트림 처리용 #####################################################
from flask_socketio import SocketIO
from LMS.service.AiStreamService import AiStreamService
import os


# 2. async_mode='eventlet' 명시 (실시간 스트리밍 안정성 확보)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- AI 탐지 라우트 ---
@app.route('/ai-detect/aistream')
def ai_stream():
    return render_template('ai_detect/ai_stream.html')

def run_ai_logic():
    # RTSP 주소 확인
    RTSP_URL = "rtsp://admin:Mbc320!!@192.168.0.14:554/stream1"
    print(f"[SYSTEM] AI Background Task Start")
    AiStreamService.run_rtsp_stream(socketio, RTSP_URL)

@socketio.on('connect')
def handle_connect():
    # 사용자가 접속하면 AI 스트림 시작
    socketio.start_background_task(run_ai_logic)

@socketio.on('set_detection_target')
def handle_target(data):
    target = data.get('target', '')
    AiStreamService.set_target(target)

# ---------------------------------------------------------
# 4. 서버 실행
# ---------------------------------------------------------
if __name__ == '__main__':
    # debug=False로 해야 라우트 꼬임이 없습니다.
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)