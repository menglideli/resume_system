"""统一导出所有 ORM 模型（确保关系注册）。"""
from app.models.application import Application
from app.models.certification import Certification
from app.models.custom_field_def import CustomFieldDef
from app.models.education import Education
from app.models.family import FamilyMember
from app.models.form import FormModel
from app.models.interview_prep import InterviewPrep
from app.models.photo import Photo
from app.models.job_description import JobDescription
from app.models.profile import Profile
from app.models.profile_block import ProfileBlock, ProfileBlockEntry
from app.models.project import Project
from app.models.resume import Resume
from app.models.resume_version import ResumeVersion
from app.models.skill import Skill
from app.models.system_config import SystemConfig
from app.models.user import User
from app.models.work import WorkExperience

__all__ = [
    "Application", "Certification", "CustomFieldDef", "Education", "FamilyMember", "FormModel",
    "InterviewPrep", "JobDescription", "Photo", "Profile", "ProfileBlock", "ProfileBlockEntry", "Project",
    "Resume", "ResumeVersion", "Skill", "SystemConfig", "User", "WorkExperience",
]
