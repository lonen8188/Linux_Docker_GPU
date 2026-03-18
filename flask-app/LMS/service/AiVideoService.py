import json

from LMS.common.session import Session

class AiVideoService:
    @staticmethod
    def create_video_post(member_id, title, content, origin_path):
        conn = Session.get_connection()
        cursor = conn.cursor()
        try:
            sql = """
                INSERT INTO ai_video_posts (member_id, title, content, origin_video_path, status)
                VALUES (%s, %s, %s, %s, 'PENDING')
            """
            cursor.execute(sql, (int(member_id), title, content, origin_path))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            print(f"Video DB 저장 실패: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def save_video_detail(video_post_id, frame_num, objects_json):
        conn = Session.get_connection()
        cursor = conn.cursor()
        try:
            sql = "INSERT INTO ai_video_details (video_post_id, frame_number, detected_objects) VALUES (%s, %s, %s)"
            cursor.execute(sql, (video_post_id, frame_num, json.dumps(objects_json)))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def update_video_status(video_id, status, result_path, total_frames):
        conn = Session.get_connection()
        cursor = conn.cursor()
        try:
            sql = """
                    UPDATE ai_video_posts 
                    SET status = %s, result_video_path = %s, total_frames = %s 
                    WHERE id = %s
                """
            cursor.execute(sql, (status, result_path, total_frames, video_id))
            conn.commit()
        finally:
            cursor.close()
            conn.close()