"""导入全部模型，确保注册到 Base.metadata"""
from app.models.user import User
from app.models.subject import Subject
from app.models.chapter import Chapter
from app.models.page import Page
from app.models.quiz import QuizQuestion, QuizSession
# T12-0：整章整理结果表（必须导入，否则 create_all 不知道这张表）
from app.models.chapter_organization import ChapterOrganization
