# 상품 이미지용 테이블 추가
# CREATE TABLE item_images (
#     id         INT AUTO_INCREMENT PRIMARY KEY,
#     item_id    INT NOT NULL,
#     image_path VARCHAR(255) NOT NULL, -- 이미지 저장 경로 또는 URL
#     is_main    BOOLEAN DEFAULT FALSE, -- 대표 이미지 여부
#     created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
#
#     FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
# );


class Item:
    # 카테고리 상수 및 리스트 정의
    CATEGORY_ETC = "잡화"
    CATEGORY_DRINK = "음료"
    CATEGORY_IT = "IT"
    CATEGORY_BOOK = "도서"

    # 서비스에서 메뉴를 뿌릴 때 사용할 리스트
    CATEGORIES = [CATEGORY_ETC, CATEGORY_DRINK, CATEGORY_IT, CATEGORY_BOOK]

    def __init__(self, id=None, code=None, name=None, category=None,
                 price=0, stock=0, created_at=None, images=None, main_image=None):
        self.id = id
        self.code = code
        self.name = name
        self.category = category
        self.price = price
        self.stock = stock
        self.created_at = created_at
        self.images = images if images else []  # 전체 이미지 리스트
        self.main_image = main_image            # 대표 이미지 경로

    @classmethod
    def from_db(cls, row: dict, images=None):
        if not row: return None
        return cls(
            id=row.get('id'),
            code=row.get('code'),
            name=row.get('name'),
            category=row.get('category'),
            price=int(row.get('price', 0)),
            stock=int(row.get('stock', 0)),
            created_at=row.get('created_at'),
            images=images, # 이미지 리스트 주입
            main_image=row.get('main_image')
        )