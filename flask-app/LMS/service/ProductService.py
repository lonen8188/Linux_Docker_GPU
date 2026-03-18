from LMS.common.session import Session
from LMS.domain.item import Item

class ProductService:

    @staticmethod
    def create_item_from_form(form_data):
        return Item(
            code=form_data.get('code'),
            name=form_data.get('name'),
            category=form_data.get('category'),
            price=int(form_data.get('price', 0)),
            stock=int(form_data.get('stock', 0))
        )

    @staticmethod
    def calculate_total_stock_value(items):
        """
        보유한 상품 객체 리스트를 받아 전체 재고 자산 가치를 계산합니다.
        (DB 조회가 필요 없으므로 staticmethod가 적합)
        """
        return sum(item.price * item.stock for item in items)

    @staticmethod
    def validate_item_data(data):
        """
        입력 데이터의 유효성을 검사합니다.
        """
        if not data.get('code') or int(data.get('price', 0)) < 0:
            return False
        return True

    @staticmethod
    def get_all_products():
        """전체 상품 및 대표 이미지 조회 (정적 메서드)"""
        conn = Session.get_connection()
        # dict 형식으로 결과를 받기 위해 dictionary=True 커서를 사용하는 것이 좋습니다.
        # (만약 일반 커서를 쓰신다면 row[0] 등으로 접근해야 하니 주의하세요!)
        cursor = conn.cursor()

        try:
            # items(i)와 item_images(img)를 조인하여 대표 이미지만 가져옵니다.
            query = """
                    SELECT i.*, img.image_path AS main_image  -- 반드시 'AS main_image'가 있어야 함!
                    FROM items i
                    LEFT JOIN item_images img ON i.id = img.item_id AND img.is_main = 1
                    ORDER BY i.id DESC
                """
            cursor.execute(query)
            rows = cursor.fetchall()

            # Item 객체 리스트로 변환하여 반환
            return [Item.from_db(row) for row in rows]

        except Exception as e:
            print(f"상품 목록 조회 오류: {e}")
            return []
        finally:
            cursor.close()

    @staticmethod
    def register_product(item_obj, image_paths):
        # 1. 커넥션 가져오기
        conn = Session.get_connection()
        # 2. 커서 생성 (실제 실행을 담당)
        cursor = conn.cursor()

        try:
            # 3. 상품 정보 저장 (cursor.execute 사용)
            query = """
                    INSERT INTO items (code, name, category, price, stock)
                    VALUES (%s, %s, %s, %s, %s)
                """
            cursor.execute(query, (
                item_obj.code, item_obj.name, item_obj.category,
                item_obj.price, item_obj.stock
            ))

            # 방금 삽입된 item의 id 가져오기
            item_id = cursor.lastrowid

            # 4. 이미지 경로 저장
            if image_paths:
                img_query = "INSERT INTO item_images (item_id, image_path, is_main) VALUES (%s, %s, %s)"

                for i, path in enumerate(image_paths):
                    # i가 0이면(첫 번째 이미지) is_main=1, 나머지는 0
                    is_main = 1 if i == 0 else 0
                    cursor.execute(img_query, (item_id, path, is_main))

            # 5. 성공 시 커넥션에서 commit 호출
            conn.commit()
            return True

        except Exception as e:
            # 에러 발생 시 rollback
            conn.rollback()
            print(f"등록 오류 상세: {e}")
            return False

        finally:
            # 6. 커서 닫기
            cursor.close()

    @staticmethod
    def get_product_by_id(item_id):
        """상품 상세 정보 및 모든 이미지 조회"""
        conn = Session.get_connection()
        cursor = conn.cursor()

        try:
            # 1. 상품 기본 정보 가져오기
            cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
            item_row = cursor.fetchone()

            if not item_row:
                return None

            # 2. 해당 상품의 모든 이미지 경로 가져오기 (is_main 순서대로 정렬)
            cursor.execute("""
                SELECT image_path, is_main 
                FROM item_images 
                WHERE item_id = %s ORDER BY is_main DESC, id ASC""", (item_id,))
            image_rows = cursor.fetchall()

            # 이미지 경로들만 리스트로 추출
            image_list = [row['image_path'] for row in image_rows]

            # [중요] 대표 이미지(main_image)를 명시적으로 row에 넣어줍니다.
            # is_main=1인 이미지가 있다면 그 녀석을, 없다면 첫 번째 이미지를 사용합니다.
            main_img = next((row['image_path'] for row in image_rows if row['is_main'] == 1), None)
            if not main_img and image_list:
                main_img = image_list[0]

            item_row['main_image'] = main_img  # 이 값이 있어야 Item.from_db에서 인식함!
            return Item.from_db(item_row, images=image_list)

        finally:
            cursor.close()

    @staticmethod
    def update_product(item_id, item_data, new_images=None):
        conn = Session.get_connection()
        cursor = conn.cursor()

        try:
            # 1. 기본 정보 업데이트 (이름, 가격, 재고, 카테고리 등)
            sql = """
                UPDATE items 
                SET name=%s, price=%s, stock=%s, category=%s, code=%s 
                WHERE id=%s
            """
            cursor.execute(sql, (
                item_data['name'], item_data['price'],
                item_data['stock'], item_data['category'],
                item_data['code'], item_id
            ))

            # 2. 새 이미지가 업로드된 경우 처리 (간단하게 추가하는 방식)
            if new_images:
                for img_path in new_images:
                    cursor.execute(
                        "INSERT INTO item_images (item_id, image_path) VALUES (%s, %s)",
                        (item_id, img_path)
                    )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"수정 에러: {e}")
            return False
        finally:
            cursor.close()

    @staticmethod
    def delete_product_with_files(item_id):
        conn = Session.get_connection()
        cursor = conn.cursor()

        try:
            # 1. 삭제 전, 서버에서 지워야 할 이미지 경로들 미리 백업
            cursor.execute("SELECT image_path FROM item_images WHERE item_id = %s", (item_id,))
            images = cursor.fetchall()

            # 2. 상품 삭제 (CASCADE 설정 덕분에 item_images, order_items 등도 자동 삭제됨)
            cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))

            conn.commit()
            return True, images
        except Exception as e:
            conn.rollback()
            print(f"DB 삭제 에러: {e}")
            return False, []
        finally:
            cursor.close()