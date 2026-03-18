# models/post.py (예시)
class Post:
    def __init__(self, id, member_id, title, content, view_count=0, created_at=None, writer_name=None):
        self.id = id
        self.member_id = member_id
        self.title = title
        self.content = content
        self.view_count = view_count
        self.created_at = created_at
        self.writer_name = writer_name  # JOIN을 통해 가져올 작성자 이름