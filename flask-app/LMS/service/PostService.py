import os
import uuid
from LMS.common.session import Session
from datetime import datetime


class PostService:

    # 파일게시물 저장
    @staticmethod
    # def save_post(member_id, title, content, file=None, upload_folder='uploads/'):
    def save_post(member_id, title, content, files=None, upload_folder='uploads/'):
        """게시글과 첨부파일을 동시에 저장 (트랜잭션 처리)"""
        conn = Session.get_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 게시글(posts) 먼저 저장
                sql_post = "INSERT INTO posts (member_id, title, content) VALUES (%s, %s, %s)"
                cursor.execute(sql_post, (member_id, title, content))

                # 방금 인서트된 게시글의 ID(PK) 가져오기
                post_id = cursor.lastrowid

                # 2. 단일 파일이 있다면 처리
                # if file and file.filename != '':
                #     origin_name = file.filename
                #     # 확장자 추출 및 중복 방지용 이름 생성
                #     ext = origin_name.rsplit('.', 1)[1].lower()
                #     save_name = f"{uuid.uuid4().hex}.{ext}"
                #     file_path = os.path.join(upload_folder, save_name)
                #
                #     # 서버 폴더에 실제 파일 저장
                #     file.save(file_path)
                #
                #     # DB에 파일 정보(attachments) 저장
                #     sql_file = """
                #         INSERT INTO attachments (post_id, origin_name, save_name, file_path, file_size)
                #         VALUES (%s, %s, %s, %s, %s)
                #     """
                #     # f.seek(0, 2) 등으로 사이즈를 구할 수 있으나 간단히 0 처리 또는 생략 가능
                #     cursor.execute(sql_file, (post_id, origin_name, save_name, file_path, 0))

                # 3. 다중 파일 처리
                if files:
                    for file in files:
                        if file and file.filename != '':
                            origin_name = file.filename
                            ext = origin_name.rsplit('.', 1)[1].lower()
                            save_name = f"{uuid.uuid4().hex}.{ext}"
                            file_path = os.path.join(upload_folder, save_name)

                            file.save(file_path)  # 서버에 저장

                            # attachments 테이블에 각각 저장
                            sql_file = """
                                                INSERT INTO attachments (post_id, origin_name, save_name, file_path)
                                                VALUES (%s, %s, %s, %s)
                                            """
                            cursor.execute(sql_file, (post_id, origin_name, save_name, file_path))

                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving post: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # 파일게시물 목록
    @staticmethod
    def get_posts():
        """작성자 이름과 첨부파일 개수를 함께 조회"""
        conn = Session.get_connection()
        try:
            with conn.cursor() as cursor:
                # 서브쿼리를 사용하여 해당 게시글에 연결된 첨부파일 개수(file_count)를 가져옵니다.
                sql = """
                        SELECT p.*, m.name as writer_name,
                               (SELECT COUNT(*) FROM attachments WHERE post_id = p.id) as file_count
                        FROM posts p
                        JOIN members m ON p.member_id = m.id
                        ORDER BY p.created_at DESC
                    """
                cursor.execute(sql)
                return cursor.fetchall()
        finally:
            conn.close()

    # 파일게시물 자세히보기
    @staticmethod
    def get_post_detail(post_id):
        """게시글 상세 정보와 첨부파일 정보를 함께 조회"""
        conn = Session.get_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 조회수 증가
                cursor.execute("UPDATE posts SET view_count = view_count + 1 WHERE id = %s", (post_id,))

                # 2. 게시글 정보 조회 (작성자 이름 포함)
                sql_post = """
                        SELECT p.*, m.name as writer_name 
                        FROM posts p
                        JOIN members m ON p.member_id = m.id
                        WHERE p.id = %s
                    """
                cursor.execute(sql_post, (post_id,))
                post = cursor.fetchone()

                # 3. 첨부파일 정보 조회
                cursor.execute("SELECT * FROM attachments WHERE post_id = %s", (post_id,))
                files = cursor.fetchall()

                conn.commit()
                return post, files
        finally:
            conn.close()

    # 단일 파일게시물 수정 페이지
    # @staticmethod
    # def update_post(post_id, title, content, file=None, upload_folder='uploads/'):
    #     """게시글 수정 및 파일 교체 로직"""
    #     conn = Session.get_connection()
    #     try:
    #         with conn.cursor() as cursor:
    #             # 1. 기본 정보(제목, 내용) 업데이트
    #             sql = "UPDATE posts SET title=%s, content=%s WHERE id=%s"
    #             cursor.execute(sql, (title, content, post_id))
    #
    #             # 2. 새 파일이 업로드된 경우
    #             if file and file.filename != '':
    #                 # [기존 파일 삭제 로직 추가 가능] - 일단 DB 정보 교체 중심
    #                 origin_name = file.filename
    #                 ext = origin_name.rsplit('.', 1)[1].lower()
    #                 save_name = f"{uuid.uuid4().hex}.{ext}"
    #                 file_path = os.path.join(upload_folder, save_name)
    #                 file.save(file_path)
    #
    #                 # 기존 첨부파일이 있는지 확인
    #                 cursor.execute("SELECT id FROM attachments WHERE post_id = %s", (post_id,))
    #                 existing_file = cursor.fetchone()
    #
    #                 if existing_file:
    #                     # 기존 정보가 있으면 UPDATE
    #                     sql_file = "UPDATE attachments SET origin_name=%s, save_name=%s, file_path=%s WHERE post_id=%s"
    #                     cursor.execute(sql_file, (origin_name, save_name, file_path, post_id))
    #                 else:
    #                     # 기존에 파일이 없었으면 INSERT
    #                     sql_file = "INSERT INTO attachments (post_id, origin_name, save_name, file_path) VALUES (%s, %s, %s, %s)"
    #                     cursor.execute(sql_file, (post_id, origin_name, save_name, file_path))
    #
    #             conn.commit()
    #             return True
    #     except Exception as e:
    #         print(f"Update Error: {e}")
    #         conn.rollback()
    #         return False
    #     finally:
    #         conn.close()

    @staticmethod # 다중파일 수정 처리(기존파일 지우고 업데이트)
    def update_post(post_id, title, content, files=None, upload_folder='uploads/'):
        """게시글 수정 및 다중 파일 교체"""
        conn = Session.get_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 기본 정보 수정
                cursor.execute("UPDATE posts SET title=%s, content=%s WHERE id=%s", (title, content, post_id))

                # 2. 새 파일들이 들어왔을 경우만 기존 파일 삭제 및 교체
                # (아무 파일도 선택 안 하면 기존 파일 유지)
                if files and any(f.filename != '' for f in files):
                    # A. 기존 물리적 파일 삭제를 위해 save_name 조회
                    cursor.execute("SELECT save_name FROM attachments WHERE post_id = %s", (post_id,))
                    old_files = cursor.fetchall()
                    for old in old_files:
                        old_path = os.path.join(upload_folder, old['save_name'])
                        if os.path.exists(old_path):
                            os.remove(old_path)

                    # B. DB에서 기존 첨부파일 기록 삭제
                    cursor.execute("DELETE FROM attachments WHERE post_id = %s", (post_id,))

                    # C. 새로운 파일들 저장
                    for file in files:
                        if file and file.filename != '':
                            origin_name = file.filename
                            ext = origin_name.rsplit('.', 1)[1].lower()
                            save_name = f"{uuid.uuid4().hex}.{ext}"
                            file_path = os.path.join(upload_folder, save_name)
                            file.save(file_path)

                            cursor.execute("""
                                    INSERT INTO attachments (post_id, origin_name, save_name, file_path)
                                    VALUES (%s, %s, %s, %s)
                                """, (post_id, origin_name, save_name, file_path))

                conn.commit()
                return True
        except Exception as e:
            print(f"Update Error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    @staticmethod
    def delete_post(post_id, upload_folder='uploads/'):
        """게시글 및 관련 실제 파일 삭제"""
        conn = Session.get_connection()
        try:
            with conn.cursor() as cursor:
                # 1. 삭제 전 첨부파일 정보 조회 (파일 삭제를 위해)
                cursor.execute("SELECT save_name FROM attachments WHERE post_id = %s", (post_id,))
                files = cursor.fetchall()

                # 2. 서버에서 실제 파일 삭제
                for f in files:
                    file_path = os.path.join(upload_folder, f['save_name'])
                    if os.path.exists(file_path):
                        os.remove(file_path)

                # 3. 게시글 삭제 (DB 외래키 ON DELETE CASCADE 설정 덕분에 attachments도 자동 삭제됨)
                sql = "DELETE FROM posts WHERE id = %s"
                cursor.execute(sql, (post_id,))

                conn.commit()
                return True
        except Exception as e:
            print(f"Delete Error: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
