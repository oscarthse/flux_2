"""
Employee and scheduling models.
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Numeric, Date, Time, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from src.db.base import Base


class EmployeeRole(Base):
    """Role/position types (Chef, Server, Bartender, Host)."""
    __tablename__ = "employee_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    hourly_rate_default = Column(Numeric(10, 2))
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")
    employees = relationship("Employee", back_populates="role")


class Employee(Base):
    """Staff member of a restaurant."""
    __tablename__ = "employees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    role_id = Column(UUID(as_uuid=True), ForeignKey("employee_roles.id", ondelete="SET NULL"))
    hourly_rate = Column(Numeric(10, 2), nullable=False)
    min_hours_per_week = Column(Numeric(5, 2), default=0)
    max_hours_per_week = Column(Numeric(5, 2), default=40)
    hire_date = Column(Date)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")
    user = relationship("User")
    role = relationship("EmployeeRole", back_populates="employees")
    skills = relationship("EmployeeSkill", back_populates="employee", cascade="all, delete-orphan")
    availability = relationship("EmployeeAvailability", back_populates="employee", cascade="all, delete-orphan")
    scheduled_shifts = relationship("ScheduledShift", back_populates="employee")


class Skill(Base):
    """Skills or certifications (Grill, Bar, Food Safety, etc.)."""
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")


class EmployeeSkill(Base):
    """Junction table for employee skills."""
    __tablename__ = "employee_skills"

    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    certified_date = Column(Date)
    expiry_date = Column(Date)

    employee = relationship("Employee", back_populates="skills")
    skill = relationship("Skill")


class ShiftTemplate(Base):
    """Recurring shift patterns."""
    __tablename__ = "shift_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    required_staff = Column(Integer, default=1)
    required_skill_id = Column(UUID(as_uuid=True), ForeignKey("skills.id", ondelete="SET NULL"))
    days_of_week = Column(ARRAY(Integer))  # [1,2,3,4,5] = Mon-Fri
    created_at = Column(DateTime, server_default=func.now())

    restaurant = relationship("Restaurant")
    required_skill = relationship("Skill")


class EmployeeAvailability(Base):
    """When employees can work."""
    __tablename__ = "employee_availability"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Sunday, 6=Saturday
    start_time = Column(Time)
    end_time = Column(Time)
    is_available = Column(Boolean, default=True)
    preference = Column(Integer, default=0)  # -1=prefer not, 0=neutral, 1=prefer
    effective_from = Column(Date, server_default=func.current_date())
    effective_to = Column(Date)
    created_at = Column(DateTime, server_default=func.now())

    employee = relationship("Employee", back_populates="availability")


class ScheduledShift(Base):
    """Actual scheduled work assignments."""
    __tablename__ = "scheduled_shifts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    shift_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("employee_roles.id", ondelete="SET NULL"))
    status = Column(String(20), default="scheduled")  # scheduled, confirmed, completed, no_show
    actual_start_time = Column(Time)
    actual_end_time = Column(Time)
    notes = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant")
    employee = relationship("Employee", back_populates="scheduled_shifts")
    role = relationship("EmployeeRole")
