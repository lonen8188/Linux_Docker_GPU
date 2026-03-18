from LMS.common.session import Session

class AiDetectService:
    @staticmethod
    def save_detect_post(member_id, title, content, image_path, result_json):
        conn = Session.get_connection()
        cursor = conn.cursor()
        sql = """INSERT INTO ai_detect_posts 
                 (member_id, title, content, image_path, detect_result) 
                 VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(sql, (member_id, title, content, image_path, result_json))
        conn.commit()
        cursor.close()

    @staticmethod
    def get_all_posts():
        conn = Session.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_detect_posts ORDER BY id DESC")
        return cursor.fetchall()