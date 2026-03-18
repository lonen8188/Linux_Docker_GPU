from LMS.common.session import Session


class OrderService:
    @staticmethod
    def create_order(member_id, item_id, quantity):
        conn = Session.get_connection()
        cursor = conn.cursor()

        try:
            # 1. 재고 확인 및 상품 가격 가져오기
            cursor.execute("SELECT price, stock FROM items WHERE id = %s FOR UPDATE", (item_id,))
            item = cursor.fetchone()

            if not item or item['stock'] < quantity:
                return False, "재고가 부족합니다."

            # 2. orders 테이블 삽입 (총 금액 계산: 가격 * 수량)
            total_price = item['price'] * quantity
            cursor.execute(
                "INSERT INTO orders (member_id, total_price) VALUES (%s, %s)",
                (member_id, total_price)
            )
            order_id = cursor.lastrowid

            # 3. order_items 테이블 삽입
            cursor.execute(
                "INSERT INTO order_items (order_id, item_id, qty, price) VALUES (%s, %s, %s, %s)",
                (order_id, item_id, quantity, item['price'])
            )

            # 4. 재고 차감 (매우 중요!)
            cursor.execute(
                "UPDATE items SET stock = stock - %s WHERE id = %s",
                (quantity, item_id)
            )

            # 모든 작업 성공 시 확정
            conn.commit()
            return True, "주문이 완료되었습니다."

        except Exception as e:
            conn.rollback()
            print(f"주문 에러: {e}")
            return False, "주문 처리 중 오류가 발생했습니다."
        finally:
            cursor.close()



    @staticmethod
    def checkout(member_id, cart_data): # 최종 주문
        """
        cart_data 형식: {'1': 2, '5': 1} (item_id: quantity)
        """
        if not cart_data:
            return False, "장바구니가 비어 있습니다."

        conn = Session.get_connection()
        cursor = conn.cursor()

        try:
            # 1. 먼저 전체 총액 계산 (검증 포함)
            total_order_price = 0
            order_items_to_process = []

            for item_id, qty in cart_data.items():
                cursor.execute("SELECT id, price, stock, name FROM items WHERE id = %s FOR UPDATE", (item_id,))
                item = cursor.fetchone()

                if not item: continue
                if item['stock'] < qty:
                    return False, f"[{item['name']}]의 재고가 부족합니다."

                subtotal = item['price'] * qty
                total_order_price += subtotal
                order_items_to_process.append({
                    'item_id': item['id'],
                    'qty': qty,
                    'price': item['price']
                })

            # 2. orders 테이블 삽입
            cursor.execute(
                "INSERT INTO orders (member_id, total_price) VALUES (%s, %s)",
                (member_id, total_order_price)
            )
            new_order_id = cursor.lastrowid

            # 3. order_items 삽입 및 재고 차감
            for oi in order_items_to_process:
                # 상세 내역 저장
                cursor.execute(
                    "INSERT INTO order_items (order_id, item_id, qty, price) VALUES (%s, %s, %s, %s)",
                    (new_order_id, oi['item_id'], oi['qty'], oi['price'])
                )
                # 재고 업데이트
                cursor.execute(
                    "UPDATE items SET stock = stock - %s WHERE id = %s",
                    (oi['qty'], oi['item_id'])
                )

            conn.commit()
            return True, "주문이 성공적으로 완료되었습니다."

        except Exception as e:
            conn.rollback()
            print(f"체크아웃 에러: {e}")
            return False, "주문 처리 중 오류가 발생했습니다."
        finally:
            cursor.close()

    @staticmethod
    def get_member_orders(member_id): # 주문 내역보기용
        conn = Session.get_connection()
        cursor = conn.cursor()

        try:
            # 주문 요약 정보와 첫 번째 상품명을 대표로 가져오는 쿼리
            # (더 상세하게 하려면 order_items를 따로 또 조회해야 하지만, 우선 목록부터!)
            sql = """
                SELECT o.id, o.total_price, o.created_at,
                       (SELECT i.name FROM order_items oi 
                        JOIN items i ON oi.item_id = i.id 
                        WHERE oi.order_id = o.id LIMIT 1) as representative_name,
                       (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
                FROM orders o
                WHERE o.member_id = %s
                ORDER BY o.created_at DESC
            """
            cursor.execute(sql, (member_id,))
            return cursor.fetchall()
        finally:
            cursor.close()

    @staticmethod
    def get_order_detail(order_id, member_id):
        conn = Session.get_connection()
        cursor = conn.cursor()

        try:
            # 1. 주문 기본 정보 가져오기 (본인 주문인지 확인하기 위해 member_id 체크)
            cursor.execute("SELECT * FROM orders WHERE id = %s AND member_id = %s", (order_id, member_id))
            order = cursor.fetchone()

            if not order:
                return None, None

            # 2. 해당 주문의 상세 상품 목록 가져오기 (items 테이블과 조인)
            sql = """
                SELECT oi.*, i.name, i.code, 
                       (SELECT image_path FROM item_images WHERE item_id = i.id LIMIT 1) as main_image
                FROM order_items oi
                JOIN items i ON oi.item_id = i.id
                WHERE oi.order_id = %s
            """
            cursor.execute(sql, (order_id,))
            items = cursor.fetchall()

            return order, items
        finally:
            cursor.close()