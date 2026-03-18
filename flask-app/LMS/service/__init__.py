from LMS.service.MemberService import MemberService
from LMS.service.ScoreService import ScoreService
from LMS.service.BoardService import BoardService
from LMS.service.PostService import PostService
from LMS.service.ProductService import ProductService
from LMS.service.OrderService import OrderService
#    최상위       파일명(모듈)          클래스명

# 다른 패키지에서 import *로 처리 가능
__all__ = ['MemberService', 'ScoreService', 'BoardService', 'PostService', 'ProductService' , 'OrderService']